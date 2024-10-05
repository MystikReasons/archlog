
# Quickstart
`pip install -r requirements.txt`

## Build documentation with Sphinx
If no /docs folder is available use the following command
    - sudo docker run -it --rm -v $(pwd)/docs:/docs sphinxdoc/sphinx sphinx-quickstart

Once that is available, you can for example generate a .html file with
    - sudo docker run --rm -v $(pwd)/docs:/docs sphinxdoc/sphinx make html
