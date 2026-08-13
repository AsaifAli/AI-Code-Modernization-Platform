from fpdf import FPDF
import re
class MarkdownPDF(FPDF):
    def write_markdown_style_text(self, text):
        """
        Render simple Markdown-style text:
        - # Heading 1
        - ## Heading 2
        - **Bold**
        - _Italic_
        - Normal text
        """
        # Italic
        self.add_font(
                     family="DejaVuSans",
                     style="",
                     fname=f"{prepath}/DejaVuSans.ttf",
                     uni=True
                 )
        
        # Bold
        self.add_font(
           family="DejaVuSans",
           style="B",
           fname=f"{prepath}/DejaVuSans-Bold.ttf",
           uni=True
        )
        
        # Italic
        self.add_font(
            family="DejaVuSans",
            style="I",
            fname=f"{prepath}/DejaVuSans-Oblique.ttf",
            uni=True
        )
       
        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                self.ln(8)
                continue

            # Detect heading levels
            if line.startswith("###"):
                self.set_font("DejaVuSans", "B", 14)
                self.cell(0, 10, line.lstrip("#").strip(), ln=True)
                self.ln(2)
            elif line.startswith("##"):
                self.set_font("DejaVuSans", "B", 16)
                self.cell(0, 10, line.lstrip("#").strip(), ln=True)
                self.ln(3)
            elif line.startswith("#"):
                self.set_font("DejaVuSans", "B", 20)
                self.cell(0, 12, line.lstrip("#").strip(), ln=True)
                self.ln(4)
            else:
                # Regular text with bold and italic patterns
                self.set_font("DejaVuSans", size=12)
                parts = re.split(r"(\*\*.*?\*\*|_.*?_)", line)
                for part in parts:
                    if part.startswith("**") and part.endswith("**"):
                        self.set_font("DejaVuSans", "B", 12)
                        self.write(8, part.strip("*"))
                        self.set_font("DejaVuSans", size=12)
                    elif part.startswith("_") and part.endswith("_"):
                        self.set_font("DejaVuSans", "I", 12)
                        self.write(8, part.strip("_"))
                        self.set_font("DejaVuSans", size=12)
                    else:
                        self.write(8, part)
                self.ln(8)

prepath = "application/fonts"