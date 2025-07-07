from __future__ import annotations

import datetime
import xml.dom.minidom as minidom
from textwrap import dedent
from typing import Any
from xml.parsers import expat

import pdfnaut
from pdfnaut.common.dates import encode_iso8601, parse_iso8601
from pdfnaut.cos.objects import PdfDictionary, PdfName, PdfStream
from pdfnaut.exceptions import PdfParseError
from pdfnaut.objects.trailer import TrappedState

namespaces = {
    "pdf": "http://ns.adobe.com/pdf/1.3/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
}


def get_full_text(element: minidom.Element) -> str:
    """Returns the full text content within ``element``."""

    text_values = []

    for node in element.childNodes:
        if isinstance(node, minidom.Text):
            text_values.append(node.data)
        elif hasattr(node, "childNodes"):
            text_values.append(get_full_text(node))

    return "".join(text_values)


def lookup_prefix_for_ns(node: minidom.Node, namespace: str) -> tuple[str, minidom.Node] | None:
    """Locates a namespace prefix matching the ``namespace`` URI. Returns either
    a tuple of two items containing, in order, the prefix of the namespace URI and the
    node where it was found, or None, if no prefix is registered for the namespace URI.

    This is an implementation of https://dom.spec.whatwg.org/#locate-a-namespace-prefix.
    """

    if isinstance(node, minidom.Element):
        if node.namespaceURI == namespace and node.prefix:
            return (node.prefix, node)

        for attrib in node.attributes.values():
            if attrib.prefix == "xmlns" and attrib.value == namespace:
                return (attrib.localName, node)

        if node.parentNode:
            return lookup_prefix_for_ns(node.parentNode, namespace)
    elif isinstance(node, minidom.Document):
        if node.ownerDocument is None:
            return

        return lookup_prefix_for_ns(node.ownerDocument, namespace)
    elif isinstance(node, (minidom.DocumentFragment, minidom.DocumentType)):
        return
    elif isinstance(node, minidom.Attr):
        if node.ownerElement is None:
            return

        return lookup_prefix_for_ns(node.ownerElement, namespace)
    elif node.parentNode is not None:
        return lookup_prefix_for_ns(node.parentNode, namespace)


class XMPProperty:
    """An XMP property included in an XMP packet."""

    def __init__(self, namespace_uri: str, local_name: str, **extra: Any) -> None:
        self.namespace_uri = namespace_uri
        """The namespace URI of this property."""

        self.local_name = local_name
        """The local name of this property."""

        self.extra = extra
        """Any additional property-specific values."""

        self._xml_property: minidom.Element | None = None

    def _fetch_xml_property(self, xmp: XmpMetadata) -> None:
        if self._xml_property is not None:
            return

        candidates = xmp.rdf_root.getElementsByTagNameNS(self.namespace_uri, self.local_name)
        self._xml_property = candidates[0] if candidates else None

    def _set_xml_property(self, xmp: XmpMetadata, node_list: list[minidom.Node]) -> None:
        self._fetch_xml_property(xmp)

        if self._xml_property:
            # This property is present in the document.
            # Simply replace the children with a new text node.
            self._xml_property.childNodes[:] = node_list
            xmp.stream.modify(xmp.packet.toprettyxml().encode())

            return

        # We will have to make a new property
        # Let's first check the document to see if our namespace is already registered.
        prefix_and_node = lookup_prefix_for_ns(xmp.rdf_root, self.namespace_uri)
        if prefix_and_node is not None:
            prefix, element_with_prefix = prefix_and_node
        else:
            prefix, element_with_prefix = None, None

        # Then check the children
        for child in xmp.rdf_root.childNodes:
            if prefix_and_node := lookup_prefix_for_ns(child, self.namespace_uri):
                prefix, element_with_prefix = prefix_and_node
                break

        if prefix and element_with_prefix:
            # An element with this namespace is registered, create the element.
            element = xmp.packet.createElementNS(self.namespace_uri, f"{prefix}:{self.local_name}")
        else:
            # No prefix for namespace in document, register it in parent.

            prefix_by_ns = {prefix: ns for ns, prefix in namespaces.items()}
            xmp.rdf_root.setAttribute(
                f"xmlns:{prefix_by_ns[self.namespace_uri]}", self.namespace_uri
            )

            element = xmp.packet.createElementNS(
                self.namespace_uri, prefix_by_ns[self.namespace_uri] + ":" + self.local_name
            )

            element_with_prefix = xmp.rdf_root

        # Insert the new element
        element.childNodes[:] = node_list
        element_with_prefix.appendChild(element)

        xmp.stream.modify(xmp.packet.toprettyxml().encode())

    def _ensure_rdf_prefix(self, xmp: XmpMetadata) -> str:
        prefix_and_node = lookup_prefix_for_ns(xmp.rdf_root, namespaces["rdf"])

        if prefix_and_node is not None:
            prefix, _ = prefix_and_node
        else:
            xmp.rdf_root.setAttribute("xmlns:rdf", namespaces["rdf"])
            prefix = "rdf"

        return prefix

    def _delete_xml_property(self, xmp: XmpMetadata) -> None:
        self._fetch_xml_property(xmp)

        if self._xml_property is None:
            raise ValueError(
                f"No such element: {self.local_name!r} with namespace {self.namespace_uri!r}"
            )

        self._xml_property.parentNode.removeChild(self._xml_property)
        self._xml_property = None


class XMPTextProperty(XMPProperty):
    """An XMP Text property -- a possibly empty Unicode string."""

    def __get__(self, xmp: XmpMetadata, objtype: Any | None = None) -> str | None:
        self._fetch_xml_property(xmp)

        return get_full_text(self._xml_property) if self._xml_property else None

    def __set__(self, xmp: XmpMetadata, value: str) -> None:
        self._fetch_xml_property(xmp)

        text_node = xmp.packet.createTextNode(value)
        self._set_xml_property(xmp, [text_node])

    def __delete__(self, xmp: XmpMetadata) -> None:
        self._delete_xml_property(xmp)


class XMPLangAltProperty(XMPProperty):
    """An XMP Language Alternative property -- an alternative array of simple text items
    facilitating the selection of a text item based on a desired language.

    In this case, this array is represented as a mapping of language names to text items
    corresponding to each language. The language name should be a value as defined in RFC
    3066, composed of a primary language subtag and an optional series of subsequent subtags.

    The default value, if known, should be the first item in the dictionary. A default
    value may also be explicitly marked by setting its language to 'x-default'.

    See https://developer.adobe.com/xmp/docs/XMPNamespaces/XMPDataTypes/#language-alternative.
    """

    def __get__(self, xmp: XmpMetadata, objtype: Any | None) -> dict[str, str] | None:
        self._fetch_xml_property(xmp)

        if self._xml_property is None:
            return

        alt = self._xml_property.getElementsByTagNameNS(namespaces["rdf"], "Alt")
        if not alt:
            return

        langalt = {}

        for element in alt[0].getElementsByTagNameNS(namespaces["rdf"], "li"):
            langalt[element.attributes["xml:lang"].value] = get_full_text(element)

        return langalt

    def __set__(self, xmp: XmpMetadata, value: dict[str, str]) -> None:
        self._fetch_xml_property(xmp)

        prefix = self._ensure_rdf_prefix(xmp)
        alt: minidom.Element = xmp.packet.createElementNS(namespaces["rdf"], f"{prefix}:Alt")

        for lang, val in value.items():
            list_item: minidom.Element = xmp.packet.createElementNS(
                namespaces["rdf"], f"{prefix}:li"
            )
            list_item.setAttribute("xml:lang", lang)
            list_item.childNodes.append(xmp.packet.createTextNode(val))

            alt.appendChild(list_item)

        self._set_xml_property(xmp, [alt])

    def __delete__(self, xmp: XmpMetadata) -> None:
        self._delete_xml_property(xmp)


class XMPListProperty(XMPProperty):  # list being either a sequence or bag
    """An array valued XMP property -- in this context, either an RDF sequence, used
    for ordered arrays, or an RDF bag, used for unordered arrays.

    See § 7.7 "Array valued XMP properties" in Part 1 of the XMP specification.
    """

    def __get__(self, xmp: XmpMetadata, objtype: Any | None) -> list[Any] | None:
        self._fetch_xml_property(xmp)

        if self._xml_property is None:
            return

        containers = self._xml_property.getElementsByTagNameNS(
            namespaces["rdf"], self.extra["kind"]
        )
        if not containers:
            return

        items = []
        for element in containers[0].getElementsByTagNameNS(namespaces["rdf"], "li"):
            items.append(get_full_text(element))

        return items

    def __set__(self, xmp: XmpMetadata, value: list[Any]) -> None:
        self._fetch_xml_property(xmp)

        prefix = self._ensure_rdf_prefix(xmp)
        kind = self.extra["kind"]
        container: minidom.Element = xmp.packet.createElementNS(
            namespaces["rdf"], f"{prefix}:{kind}"
        )

        for item in value:
            list_item: minidom.Element = xmp.packet.createElementNS(
                namespaces["rdf"], f"{prefix}:li"
            )

            list_item.childNodes.append(xmp.packet.createTextNode(item))

            container.appendChild(list_item)

        self._set_xml_property(xmp, [container])

    def __delete__(self, xmp: XmpMetadata) -> None:
        self._delete_xml_property(xmp)


class XMPDateProperty(XMPProperty):
    """An XMP Date property -- an ISO 8601 date string, or specifically, the subset
    specified in https://www.w3.org/TR/NOTE-datetime.

    See https://developer.adobe.com/xmp/docs/XMPNamespaces/XMPDataTypes/#date.
    """

    def __get__(self, xmp: XmpMetadata, objtype: Any | None = None) -> datetime.datetime | None:
        self._fetch_xml_property(xmp)

        if self._xml_property is None:
            return

        text = get_full_text(self._xml_property)
        return parse_iso8601(text)

    def __set__(self, xmp: XmpMetadata, value: datetime.datetime) -> None:
        self._fetch_xml_property(xmp)

        text_node = xmp.packet.createTextNode(encode_iso8601(value))
        self._set_xml_property(xmp, [text_node])

    def __delete__(self, xmp: XmpMetadata) -> None:
        self._delete_xml_property(xmp)


class XmpMetadata:
    """An object representing Extensible Metadata Platform (XMP) metadata, either pertaining
    to an entire document or to a particular resource.

    For information about XMP, see https://developer.adobe.com/xmp/docs/.

    Arguments:
        stream (PdfStream, optional):
            The XMP packet to parse as a PDF stream. If ``stream`` is None,
            a new stream containing a packet will be created.

    Raises:
        PdfParseError: If ``stream`` does not contain a valid XMP packet.
    """

    def __init__(self, stream: PdfStream | None = None) -> None:
        self.stream: PdfStream
        """The XMP packet as a string."""

        if stream is None:
            self.stream = PdfStream.create(
                dedent(f"""\
                    <?xml version="1.0" ?>
                    <?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
                    <x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="pdfnaut {pdfnaut.__version__}">
                        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
                        </rdf:RDF>
                    </x:xmpmeta>
                    <?xpacket end="w"?>
                """).encode(),
                PdfDictionary(Type=PdfName(b"Metadata"), Subtype=PdfName(b"XML")),
            )
        else:
            self.stream = stream

        try:
            self.packet = minidom.parseString(self.stream.decode())
            """The XMP packet as an XML document."""
        except expat.ExpatError as exc:
            raise PdfParseError("Metadata value is not a valid XMP packet.") from exc

        self.rdf_root = self.packet.getElementsByTagNameNS(namespaces["rdf"], "RDF")[0]
        """The RDF root of the packet being parsed."""

    # * PDF namespace properties
    # * https://developer.adobe.com/xmp/docs/XMPNamespaces/pdf/
    # Note: I have also seen other properties for the PDF namespace,
    # such as Subject, Author, and Copyright. But, as far as I know,
    # they're not official and seem to stem from improper reconciling
    # of the DocInfo dictionary.

    pdf_producer = XMPTextProperty(namespaces["pdf"], "Producer")
    """The name of the tool that produced this PDF document."""

    pdf_keywords = XMPTextProperty(namespaces["pdf"], "Keywords")
    """Keywords associated with the document."""

    pdf_pdfversion = XMPTextProperty(namespaces["pdf"], "PDFVersion")
    """The PDF file version. For example, '1.0' or '1.3'."""

    _pdf_trapped_raw = XMPTextProperty(namespaces["pdf"], "Trapped")

    @property
    def pdf_trapped(self) -> TrappedState:
        """A value indicating whether the document includes trapping support."""

        if self._pdf_trapped_raw == "True":
            return TrappedState.YES
        elif self._pdf_trapped_raw == "False":
            return TrappedState.NO

        return TrappedState.UNKNOWN

    @pdf_trapped.setter
    def pdf_trapped(self, value: TrappedState) -> None:
        if value == TrappedState.YES:
            self._pdf_trapped_raw = "True"
        elif value == TrappedState.NO:
            self._pdf_trapped_raw = "False"
        elif value == TrappedState.UNKNOWN:
            try:
                del self._pdf_trapped_raw
            except ValueError:
                pass

    @pdf_trapped.deleter
    def pdf_trapped(self) -> None:
        del self._pdf_trapped_raw

    # * XMP namespace properties
    # * https://developer.adobe.com/xmp/docs/XMPNamespaces/xmp/

    xmp_creator_tool = XMPTextProperty(namespaces["xmp"], "CreatorTool")
    """The name of the first known tool that created this resource."""

    xmp_create_date = XMPDateProperty(namespaces["xmp"], "CreateDate")
    """The datetime this resource was created. This need not match the file system
    creation date."""

    xmp_metadata_date = XMPDateProperty(namespaces["xmp"], "MetadataDate")
    """The datetime this metadata was last modified. It should be the same or more
    recent than :attr:`.modify_date`."""

    xmp_modify_date = XMPDateProperty(namespaces["xmp"], "ModifyDate")
    """The datetime this resource was last modified."""

    # * Dublin Core (DC) namespace properties
    # * https://developer.adobe.com/xmp/docs/XMPNamespaces/dc/

    dc_title = XMPLangAltProperty(namespaces["dc"], "title")
    """The titles or names given to this resource as a mapping of language names to titles."""

    dc_creator = XMPListProperty(namespaces["dc"], "creator", kind="Seq")
    """The entities primarily responsible for creating this resource."""

    dc_subject = XMPListProperty(namespaces["dc"], "subject", kind="Bag")
    """The topics or descriptions specifying the content of this resource."""

    dc_description = XMPLangAltProperty(namespaces["dc"], "description")
    """Textual descriptions of this resource as a mapping of language names to items."""

    dc_rights = XMPLangAltProperty(namespaces["dc"], "rights")
    """Rights statements pertaining to this resource."""

    dc_format = XMPTextProperty(namespaces["dc"], "format")
    """The MIME type of this resource."""
