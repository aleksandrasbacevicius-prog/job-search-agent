def extract_text_from_upload(uploaded_file) -> str:
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(uploaded_file)
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages).strip()
        except Exception as exc:
            raise ValueError(f"Could not read PDF: {exc}") from exc

    elif name.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(uploaded_file)
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except Exception as exc:
            raise ValueError(f"Could not read DOCX: {exc}") from exc

    else:
        return uploaded_file.read().decode("utf-8", errors="replace").strip()
