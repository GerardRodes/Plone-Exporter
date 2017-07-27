# Plone-Exporter
Automated XML exports with a given schema

# Usage
```python

from Products.CMFCore.utils import getToolByName
import Products
import Exporter

def my_external_method(self):
  portal_url = getToolByName(self, 'portal_url')
  portal     = portal_url.getPortalObject()
  
  export = Exporter(
            portal,
            Products.EsdevenimentsAgenda.EsdevenimentsAgenda.EsdevenimentAgenda.schema, #My Archetype schema
            Products.EsdevenimentsAgenda.EsdevenimentsAgenda.EsdevenimentAgenda.EsdevenimentAgenda.meta_type #meta_type name for query catalog
          )
          
```

# Output
Creates a folder at `/tmp/exporter/{meta_type}/%Y-%m-%d_%H-%M-%S` with the following files:
- {meta_type}.xml: XML with all the contents
- log.txt: Info about the process
- files: Folder with all the attached files
