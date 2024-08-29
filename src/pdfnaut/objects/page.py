from typing import cast

from ..cos.objects.containers import PdfArray, PdfDictionary
from ..cos.objects.stream import PdfStream


class Page(PdfDictionary):
    """A page in the document (``§ 7.7.3.3 Page Objects``)."""
    def __init__(self, mapping: PdfDictionary) -> None:
        super().__init__(mapping)
        
        self.mapping = mapping

    @property
    def resources(self) -> PdfDictionary | None:
        """Resources required by the page contents. 
        
        If the page requires no resources, this returns an empty resource dictionary.
        If the page inherits its resources from an ancestor, this returns None.
        """
        if "Resources" not in self:
            return
        
        return cast(PdfDictionary, self.get("Resources"))  
    
    @property
    def mediabox(self) -> PdfArray[int]:
        """A rectangle specifying the boundaries of the physical medium in which the page
        should be printed or displayed."""
        return cast(PdfArray[int], self["MediaBox"])  

    @property
    def cropbox(self) -> PdfArray[int] | None:
        """A rectangle specifying the visible region of the page."""
        if "CropBox" not in self:
            return
        
        return cast(PdfArray[int], self["CropBox"])  
    
    @property
    def rotation(self) -> int:
        """The number of degrees by which the page shall be rotated clockwise. 
        The value is a multiple of 90 (by default, 0)."""
        return cast(int, self.get("Rotate", 0))  
    
    @property
    def metadata(self) -> PdfStream | None:
        """The number of degrees by which the page shall be rotated clockwise. 
        The value is a multiple of 90 (by default, 0)."""
        if "Metadata" not in self:
            return
        
        return cast(PdfStream, self["Metadata"])  
