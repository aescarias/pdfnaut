from __future__ import annotations

import enum
from typing import Literal

PageLayout = Literal[
    "SinglePage", "OneColumn", "TwoColumnLeft", "TwoColumnRight", "TwoPageLeft", "TwoPageRight"
]
PageMode = Literal["UseNone", "UseOutlines", "UseThumbs", "FullScreen", "UseOC", "UseAttachments"]


class UserAccessPermissions(enum.IntFlag):
    """User access permissions as specified in the P entry of the document's standard
    encryption dictionary. See "Table 22: User access permissions"."""

    PRINT = 1 << 2  # revision 3+, print may be limited by FAITHFUL_PRINT
    """Print the document. If the document uses revision 3 or later, print quality 
    may be influenced by :attr:`.FAITHFUL_PRINT`."""

    MODIFY = 1 << 3  # limited by MANAGE_ANNOTATIONS, FILL_FORM_FIELDS, and ASSEMBLE_DOCUMENT
    """Modify the contents of the document. May be influenced by :attr:`.MANAGE_ANNOTATIONS`, 
    :attr:`.FILL_FORM_FIELDS`, and :attr:`.ASSEMBLE_DOCUMENT`."""

    COPY_CONTENT = 1 << 4  # assumed as 1 by assistive technology
    """Copy or extract text and graphics. Assistive technology may assume
    this bit as 1 for its purposes, as per :attr:`.ACCESSIBILITY`."""

    MANAGE_ANNOTATIONS = 1 << 5  # affects forms too, affected by MODIFY
    """Add or modify text annotations, fill interactive form fields. And, depending 
    on whether :attr:`.MODIFY` is set, create and modify form fields."""

    FILL_FORM_FIELDS = 1 << 8  # revision 3+, overrides MODIFY
    """For documents using revision 3 or later, fill existing interactive form 
    fields, even if :attr:`.MANAGE_ANNOTATIONS` is clear."""

    ACCESSIBILITY = 1 << 9  # deprecated in PDF 2.0
    """(deprecated in PDF 2.0) Extract content for the purposes of accessibility.
    
    This bit should always be set for compatibility with processors supporting 
    earlier specifications.
    """

    ASSEMBLE_DOCUMENT = 1 << 10  # revision 3+, overrides MODIFY
    """For documents using revision 3 or later, assemble the document (i.e. insert, rotate, 
    and delete pages, create outlines, etc.), even if :attr:`.MODIFY` is clear."""

    FAITHFUL_PRINT = 1 << 11  # revision 3+
    """For documents using revision 3 or later, print the document in such a way that
    a faithful digital representation of the PDF can be generated. 
    
    If this bit is not set (and assuming :attr:`.PRINT` is also set), printing shall be 
    limited to a low-level representation, possibly of lower quality.
    """
