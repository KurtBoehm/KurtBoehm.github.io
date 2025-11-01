# Kurt Böhm’s Homepage

This is the repository for my custom-built homepage using my own Python tools.
This includes the (animated) SVG graphics, which are defined in [`generate/svgen.py`](generate/svgen.py) using [`svg.py`](https://pypi.org/project/svg.py/), a great library that makes this quite Pythonic, and [`svg-path-editor`](https://pypi.org/project/svg-path-editor/), my port of [`svg-path-editor-lib`](https://www.npmjs.com/package/svg-path-editor-lib) to Python, which is used to optimize SVG paths.
The website is generated based the HTML and Markdown files in [`src`](src) by [`make.py`](make.py) using [`make.json`](make.json).

## Dependencies

The Python dependencies used to generate the website are listed in [`requirements.txt`](requirements.txt).
I especially want to highlight [`markdown-it-py`](https://pypi.org/project/markdown-it-py/), a great library which is used to parse Markdown files.
The custom maths plugin in [`mdit_plugins`](mdit_plugins) is based on the `dollarmath` plugin in [`executablebooks/mdit-py-plugins`](https://github.com/executablebooks/mdit-py-plugins), which is licensed under the terms of the MIT licence, as provided at [`mdit_plugins/LicenseOriginal`](mdit_plugins/LicenseOriginal).

The generated website uses the following third-party resources/libraries:

- [Fira Sans](https://carrois.com/fira/), which is part of this repository at [`dist/fira-sans`](dist/fira-sans) and is licensed under the terms of the SIL Open Font licence, as provided at [`dist/fira-sans/License`](dist/fira-sans/License).
- [MathJax 4](https://www.mathjax.org/), which thankfully supports Fira Math for a consistent look.
- [Bulma 1.0.4](https://bulma.io/), which is a nice CSS framework and forms a good basis for further customizations, which are mostly contained in [`dist/kurbo.css`](dist/kurbo.css).
- [Font Awesome 7.0.1](https://fontawesome.com/), which is used by Bulma for some icons.

Additionally, [Open Color 1.9.1](https://yeun.github.io/open-color/) is used both in the Python code (with the colours defined in [`generate/open_color.py`](generate/open_color.py)) and in [`dist/kurbo.css`](dist/kurbo.css), which is licensed under the term of the MIT licence, as provided at [`generate/LicenseOpenColor`](generate/LicenseOpenColor).

# Licence

The Python, JavaScript, and CSS source files are licensed under the terms of the Mozilla Public Licence 2.0, which is provided in [`License`](License).
I reserve all rights to the actual content of the website (obviously apart from the quotes).
