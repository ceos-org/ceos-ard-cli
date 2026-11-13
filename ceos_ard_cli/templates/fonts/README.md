# Fonts

[Carlito](https://github.com/google/fonts/tree/main/ofl/carlito) is the font of the HTML and PDF documents, see [OFL.txt](OFL.txt) for its license.

The files contain all features of the original fonts and all characters except for the following Unicode blocks, which keeps the files smaller:

- Cyrillic
- Greek Extended (polytonic Greek)
- IPA Extensions and Phonetic Extensions Supplement
- Latin Extended-C and Latin Extended-D
- Modifier Tone Letters
- Combining Diacritical Marks Supplement, Combining Half Marks and Combining Diacritical Marks for Symbols

They were created with the `subset` module of [fontTools](https://github.com/fonttools/fonttools) (`flavor="woff2"`, `layout_features=["*"]`).
