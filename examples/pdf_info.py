"""This script prints information relating to the document."""

from __future__ import annotations

import sys
from getpass import getpass
from typing import cast

from pdfnaut import PdfDocument
from pdfnaut.cos.objects.containers import PdfDictionary
from pdfnaut.cos.parser import PermsAcquired
from pdfnaut.objects.catalog import PageLayout, PageMode, UserAccessPermissions

if len(sys.argv) < 2:
    sys.exit(f"usage: {sys.argv[0]} [filename]")


def humanize_page_layout(page_layout: PageLayout) -> str:
    if page_layout == "SinglePage":
        return "Single page (default)"
    elif page_layout == "OneColumn":
        return "One column"
    elif page_layout == "TwoColumnLeft":
        return "Two column, odd-numbered left"
    elif page_layout == "TwoColumnRight":
        return "Two column, odd-numbered right"
    elif page_layout == "TwoPageLeft":
        return "Two page, odd-numbered left"
    elif page_layout == "TwoPageRight":
        return "Two page, odd-numbered right"

    return f"/{page_layout}"


def humanize_page_mode(page_mode: PageMode) -> str:
    if page_mode == "FullScreen":
        return "Full-screen mode"
    elif page_mode == "UseAttachments":
        return "Attachments panel visible"
    elif page_mode == "UseNone":
        return "Default"
    elif page_mode == "UseOC":
        return "Optional content group panel visible"
    elif page_mode == "UseOutlines":
        return "Document outline visible"
    elif page_mode == "UseThumbs":
        return "Thumbnail images visible"

    return f"/{page_mode}"


def print_permissions(flags: UserAccessPermissions) -> None:
    perm_titles = {
        UserAccessPermissions.PRINT: "Print document",
        UserAccessPermissions.MODIFY: "Modify document",
        UserAccessPermissions.COPY_CONTENT: "Copy/extract content",
        UserAccessPermissions.MANAGE_ANNOTATIONS: "Manage annotations",
        UserAccessPermissions.FILL_FORM_FIELDS: "Fill form fields",
        UserAccessPermissions.ACCESSIBILITY: "Accessibility override",
        UserAccessPermissions.ASSEMBLE_DOCUMENT: "Assemble document",
        UserAccessPermissions.FAITHFUL_PRINT: "Print document in high quality",
    }

    maxlen = len(max(perm_titles.values(), key=len))

    for flag in UserAccessPermissions:
        status = "Allowed" if (flags & flag) == flag else "Not allowed"

        print(f"{perm_titles[flag]:>{maxlen}}: {status}")


def humanize_access_level(level: PermsAcquired):
    if level == PermsAcquired.OWNER:
        return "Owner (full access)"
    elif level == PermsAcquired.USER:
        return "User (under permissions)"

    return "No access"  # this one shouldn't happen though


def get_acroform_status(pdf: PdfDocument) -> str:
    acroform = cast("PdfDictionary | None", pdf.catalog.get("AcroForm"))

    if acroform is None:
        return "No"

    if "XFA" in acroform:
        return "Yes (XFA)"

    return "Yes (AcroForm)"


def get_javascript_status(pdf: PdfDocument) -> str:
    names = cast("PdfDictionary | None", pdf.catalog.get("Names"))

    if names is None:
        return "No"

    return "Yes" if "JavaScript" in names else "No"


def get_embfile_status(pdf: PdfDocument) -> str:
    names = cast("PdfDictionary | None", pdf.catalog.get("Names"))
    if names is None:
        return "No"

    return "Yes" if "EmbeddedFiles" in names else "No"


document = PdfDocument.from_filename(sys.argv[1])

if not document.access_level:
    password = getpass()
    if not document.decrypt(password):
        sys.exit("Authentication failed. Try again!")


def print_doc_info(pdf: PdfDocument) -> None:
    if document.doc_info is None:
        print("Document has no information dictionary.")
        return

    if document.doc_info.title is not None:
        print(f"Title:           {document.doc_info.title}")

    if document.doc_info.subject is not None:
        print(f"Subject:         {document.doc_info.subject}")

    if document.doc_info.author is not None:
        print(f"Author:          {document.doc_info.author}")

    if document.doc_info.keywords is not None:
        print(f"Keywords:        {document.doc_info.keywords}")

    if document.doc_info.creator is not None:
        print(f"Creator:         {document.doc_info.creator}")

    if document.doc_info.producer is not None:
        print(f"Producer:        {document.doc_info.producer}")

    if document.doc_info.creation_date is not None:
        print(f"Created:         {document.doc_info.creation_date}")

    if document.doc_info.modify_date is not None:
        print(f"Modified:        {document.doc_info.modify_date}")

    print(f"Trapping:        {document.doc_info.trapped.name}")


print_doc_info(document)

if document.language is not None:
    print(f"Language:        {document.language}")

print(f"Page Layout:     {humanize_page_layout(document.page_layout)}")
print(f"Page Mode:       {humanize_page_mode(document.page_mode)}")
print(f"Page Count:      {document.page_tree['Count']}")

print(f"PDF Version:     {document.pdf_version}")
print(f"Tagged:          {'StructTreeRoot' in document.catalog}")
print(f"Access Level:    {humanize_access_level(document.access_level)}")
print(f"Has Forms:       {get_acroform_status(document)}")
print(f"Has Javascript:  {get_javascript_status(document)}")
print(f"Has Attachments: {get_embfile_status(document)}")


if (perms := document.access_permissions) is not None:
    print("Permissions:")
    print_permissions(UserAccessPermissions(perms))
