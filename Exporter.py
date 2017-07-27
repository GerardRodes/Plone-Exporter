# -*- coding: utf-8 -*-

from xml.dom.minidom import Document
from datetime import datetime
import sys
import linecache
import os

reload(sys)
sys.setdefaultencoding('utf8')

class Exporter:

  def __init__(self, portal, schema, meta_type):
    self.portal = portal
    self.output_folder = '/tmp/exporter/' + meta_type + '/' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    self.xml_filename = meta_type + '.xml'
    self.doc = Document()
    self.contenttype_metadata = {
      'schema':    schema,
      'meta_type': meta_type,
      'fields': [],
    }

    self.create_output_files()
    self.happens('Initialized')
    self.research_fields()
    self.get_content()
    self.output_content()
    self.happens('finished!!')


  def get_content(self):
    self.content = self.portal.portal_catalog({'meta_type': self.contenttype_metadata['meta_type']})
    self.happens('Got brains (' + str(len(self.content)) + ')')


  def output_content(self):
    root = self.createChild(self.doc, 'items')
    total = str(len(self.content))
    i = 0
    for brain in self.content:
      item = self.createChild(root, 'item')
      obj  = brain.getObject()
      for field in self.contenttype_metadata['fields']: 
        try:
          value = getattr(obj, field['accessor'])()
          xml_attributes = {}
          if value:
            if field['type'] == 'file':
              if value.get_size():
                filename     = obj.getFilename(field['name'])
                content_type = obj.getContentType(field['name'])

                if not filename:
                  filename = obj.getId() + '.' + content_type.split('/')[1]

                if os.path.exists(self.output_folder + '/files/' + filename):
                  """
                    If file exists check if is has the same content, if doesn't give a new filename
                  """
                  file = open(self.output_folder + '/files/' + filename, 'r')
                  content = file.read()
                  file.close()
                  if content != str(value):
                    while os.path.exists(self.output_folder + '/files/' + filename):
                      start = filename[:3]
                      if start[0] == '(' and start[2] == ')':
                        number = int(start[1]) + 1
                        filename = filename[3:]
                      else:
                        number = 1
                      filename = '(' + str(number) + ') ' + filename

                if not os.path.exists(self.output_folder + '/files/' + filename):
                  file = open(self.output_folder + '/files/' + filename, 'w+')
                  file.write(str(value))
                  file.close()

                xml_attributes['content_type'] = content_type
                xml_attributes['filename'] = filename

                self.createChild(item, field['name'], './files/' + filename, xml_attributes)

            elif field['type'] == 'text':
              xml_attributes['content_type'] = obj.getContentType(field['name'])
              self.createChild(item, field['name'], str(value), xml_attributes)
            else:
              self.createChild(item, field['name'], str(value))

        except Exception:
          exc_type, exc_obj, tb = sys.exc_info()
          f = tb.tb_frame
          lineno = tb.tb_lineno
          filename = f.f_code.co_filename
          linecache.checkcache(filename)
          line = linecache.getline(filename, lineno)
          self.happens('Exception in line ' + str(lineno) + '\n\t' + line.strip() + '\n\t' + str(exc_obj))

      i += 1
      self.happens(str(i) + '/' + total)

    xml_file = open(self.xml_file.name, 'a')
    xml_file.write(self.doc.toprettyxml())
    xml_file.close()


  def create_output_files(self):
    folders = self.output_folder + '/files'
    if not os.path.exists(folders):
      os.makedirs(folders)

    self.log_file = open(self.output_folder + '/log.txt', 'w+')
    self.xml_file = open(self.output_folder + '/' + self.xml_filename, 'w+')
    self.log_file.close()
    self.xml_file.close()


  def research_fields(self):
    for field_instance in self.contenttype_metadata['schema'].fields():
      field = {
        'name':     field_instance.getName(),
        'type':     field_instance._properties['type'],
        'accessor': field_instance.accessor,
        'mutator':  field_instance.mutator,
      }

      if not field['accessor']:
        field['accessor'] = 'get' + field['name'][0].upper() + field['name'][1:]

      if not field['mutator']:
        field['mutator'] = 'set' + field['name'][0].upper() + field['name'][1:]

      self.contenttype_metadata['fields'].append(field)
      self.happens('Added field width data: ' + str(field))


  def createChild(self, parent, tag_name, value = None, attributes = None):
    child = self.doc.createElement(tag_name)

    if value:
      text = self.doc.createTextNode(value)
      child.appendChild(text)

    if attributes:
      for attr in attributes:
        child.setAttribute(attr, attributes[attr])

    parent.appendChild(child)
    return child


  def happens(self, msg):
    log_file = open(self.log_file.name, 'a')
    output = datetime.now().strftime('%H:%M:%S') + ' -- ' + msg + '\n'
    print output
    log_file.write(output)
    log_file.close()
