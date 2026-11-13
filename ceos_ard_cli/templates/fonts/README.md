# Fonts

[Carlito](https://github.com/google/fonts/tree/main/ofl/carlito) is the font of the HTML and PDF documents, see [OFL.txt](OFL.txt) for its license.

The files contain all characters and features of the original fonts except for Cyrillic and polytonic Greek (Greek Extended), which keeps the files smaller.
They were created with the `subset` module of [fontTools](https://github.com/fonttools/fonttools) (`flavor="woff2"`, `layout_features=["*"]`).
