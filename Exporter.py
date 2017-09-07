# -*- coding: utf-8 -*-

from plone.i18n.normalizer.interfaces import IIDNormalizer
from Products.CMFCore.interfaces import IFolderish
from Products.CMFCore.utils import getToolByName
from zope.component import getUtility
from xml.dom.minidom import Document
from datetime import datetime
import sys, linecache, Products, os, time

reload(sys)
sys.setdefaultencoding('utf8')


PLONE_TYPES = (
  'ATDocument',
  'ATFolder', 
  'ATEvent',
  'ATFavorite',
  'ATFile',
  'ATImage',
  'ATLink',
  'ATTopic',
  'ATNewsItem',
  'ATBTreeFolder',
  'FieldsetFolder',
  'FormBooleanField',
  'FormCaptchaField',
  'FormCustomScriptAdapter',
  'FormDateField',
  'FormFileField',
  'FormFixedPointField',
  'FormFolder',
  'FormIntegerField',
  'FormLabelField',
  'FormLikertField',
  'FormLinesField',
  'FormMailerAdapter',
  'FormMultiSelectionField',
  'FormPasswordField',
  'FormRichLabelField',
  'FormRichTextField',
  'FormSaveDataAdapter',
  'FormSelectionField',
  'FormStringField',
  'FormTextField',
  'FormThanksPage',
)

class Exporter:

  def __init__(self, portal, schema = None, meta_type = None, download_files = True, meta_types = tuple(), log_shows = ('event')):
    self.portal = portal
    self.log_shows = log_shows
    self.doc = Document()
    self.download_files = download_files
    self.normalizer = getUtility(IIDNormalizer)
    self.accepted_meta_types = self.test(meta_types, meta_types, PLONE_TYPES)
    self.contenttype_metadata = {}
    self.portal_workflow = getToolByName(portal, "portal_workflow")

    self.FILE_COUNT = 0

    if meta_type:
      self.output_folder = '/tmp/exporter/' + meta_type + '/' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
      self.xml_filename = meta_type + '.xml'
    elif portal:
      self.output_folder = '/tmp/exporter/' + portal.getId() + '/' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
      self.xml_filename = portal.getId() + '.xml'

    self.create_output_files()
    self.happens('Initialized', new_line=False)

    if schema and meta_type:
      self.mode = 'meta_type'
      self.contenttype_metadata = {
        'schema':    schema,
        'meta_type': meta_type,
        'fields': [],
      }
      self.research_fields()
      self.get_content()
      self.output_content()
    elif portal:
      self.mode = 'full_portal'
      self.contenttype_metadata = {}
      self.total_objects = len( self.portal.portal_catalog({
        'meta_type': {
          'query': self.accepted_meta_types
        },
        'path': {
          'query': '/'.join(self.portal.getPhysicalPath()),
          'depth': 9999,
        }
      }) )

      self.happens('%i objects matches meta types' % (self.total_objects))

      self.parsed_objects = 0
      self.dump_object(self.portal, self.createChild(self.doc, 'portal'))
      # Output XML
      xml_file = open(self.xml_file.name, 'a')
      xml_file.write(self.doc.toprettyxml())
      xml_file.close()


    # Output metadata
    metadata_file = open(self.metadata_file.name, 'w+')
    output = str(self.contenttype_metadata)
    metadata_file.write(output)
    metadata_file.close()

    self.happens('finished!!')


  def test(self, condition, true, false = None):
    # Python 2.4 doesn't have ternary operators
    if condition:
      return true
    else:
      return false


  def dump_object(self, current_object, xml_parent):
    self.parsed_objects += 1
    is_folderish = IFolderish.providedBy(current_object)
    xml_attributes = {
      'meta_type': current_object.meta_type,
      'id':        current_object.getId(),
      'path':      '/'.join(current_object.getPhysicalPath()),
      'folderish': str(is_folderish),
    }

    chain = self.portal_workflow.getChainFor(current_object)
    if len(chain) > 0:
      state = self.portal_workflow.getStatusOf(chain[0], current_object)
      if state and 'review_state' in state:
        xml_attributes['review_state'] = state['review_state']

      if hasattr(current_object, 'UID'):
        xml_attributes['uid'] = current_object.UID()

    xml_item = self.createChild(xml_parent, self.normalizer.normalize(current_object.meta_type), None, xml_attributes)

    if current_object.meta_type != 'Plone Site':
      if current_object.meta_type not in self.contenttype_metadata:
        self.happens('Adding new meta_type %s' % (current_object.meta_type))
        self.contenttype_metadata[current_object.meta_type] = {
          'schema':    current_object.schema,
          'meta_type': current_object.meta_type,
          'fields':    self.research_fields_by_schema(current_object.schema),
        }

      for field in self.contenttype_metadata[current_object.meta_type]['fields']:
        self.dump_field(current_object, xml_item, field)

    self.happens('%i/%i Added new item with id: %s' % (self.parsed_objects, self.total_objects, current_object.getId()))
    if is_folderish:
      xml_childs = self.createChild(xml_item, 'childs', None)
      childs_ids = self.test(hasattr(current_object, 'objectIds'), current_object.objectIds(), current_object.keys())

      for child_id in childs_ids:
        child = current_object.get(child_id)
        if child.meta_type in self.accepted_meta_types:
          self.dump_object(child, xml_childs)


  def dump_field(self, item, xml_item, field):
    self.happens('Reading field: ' + str(field), 'sub event')
    try:
      value = getattr(item, field['accessor'])()
      xml_attributes = {'type': field['type']}
      self.happens('Field value: ' + str(value)[:100], 'sub event')
      if value:
        if field['type'] in ('file', 'image'):
          """
            If the value is a file let's download it and relate it correctly
          """
          size = value.get_size()
          if size:
            self.happens('Files size: ' + str(size), 'sub event')
            filename     = item.getFilename(field['name']) or item.getId()
            timestamp    = str(int(round(time.time())*1000))
            content_type = item.getContentType(field['name'])
            extension    = content_type.split('/')[1]
            temp_name    = str(self.FILE_COUNT) + timestamp + '.' + extension
            self.FILE_COUNT  += 1
            if self.download_files:
              file = open(self.output_folder + '/files/' + temp_name, 'w+')
              file.write(str(value))
              file.close()

            xml_attributes['content_type'] = content_type
            xml_attributes['filename']     = filename
            xml_attributes['download_url'] = item.absolute_url() + '/at_download/' + field['name']

            self.createChild(xml_item, field['name'], './files/' + temp_name, xml_attributes)

        elif field['type'] == 'text':
          xml_attributes['content_type'] = item.getContentType(field['name'])
          self.createChild(xml_item, field['name'], str(value), xml_attributes, 'createCDATASection')

        elif isinstance(value, (list, tuple)):
          """
            If the value is a list or a tuple it will add the values in inner tags
          """
          xml_attributes['iterable'] = 'True'
          attribute = self.createChild(xml_item, field['name'], None, xml_attributes)

          attr_child_tagname = field['name'] + '_item'
          if field['name'].endswith('s'):
            attr_child_tagname = field['name'][:-1]

          for attr_child_value in value:
            self.happens('Adding child ' + str(attr_child_value) + ' to field', 'sub event')

            if field['type'] == 'reference':
              self.createChild(attribute, attr_child_tagname, attr_child_value.UID(), {'type': 'UID'})
            else: # if field['type'] == 'lines' or isinstance(attr_child_value, str):
              self.createChild(attribute, attr_child_tagname, attr_child_value)

        else:
          self.createChild(xml_item, field['name'], str(value), xml_attributes)

    except Exception:
      exc_type, exc_obj, tb = sys.exc_info()
      f = tb.tb_frame
      lineno = tb.tb_lineno
      filename = f.f_code.co_filename
      linecache.checkcache(filename)
      line = linecache.getline(filename, lineno)
      self.happens('Exception in line ' + str(lineno) + '\n\t' + line.strip() + '\n\t' + str(exc_obj))


  def get_content(self):
    self.content = self.portal.portal_catalog({'meta_type': self.contenttype_metadata['meta_type']})
    self.happens('Got brains (' + str(len(self.content)) + ')')


  def output_content(self):
    root = self.createChild(self.doc, 'items')
    total = str(len(self.content))
    i = 0
    for brain in self.content:
      """
        Every object will keep its UID as an xml attribute to follow possible references between them
      """
      obj     = brain.getObject()
      obj_uid = obj.UID()
      item    = self.createChild(root, 'item', None, {'uid': obj_uid})
      self.happens('Got object: ' + str(obj_uid) + ' - ' + brain.getPath(), 'sub event')

      for field in self.contenttype_metadata['fields']:
        self.happens('Reading field: ' + str(field), 'sub event')
        try:
          value = getattr(obj, field['accessor'])()
          xml_attributes = {'type': field['type']}
          self.happens('Field value: ' + str(value)[:100], 'sub event')
          if value:
            if field['type'] == 'file':
              """
                If the value is a file let's download it and relate it correctly
              """
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
                        filename = filename[4:]
                      else:
                        number = 1
                      filename = '(' + str(number) + ') ' + filename

                if not os.path.exists(self.output_folder + '/files/' + filename) and self.download_files:
                  file = open(self.output_folder + '/files/' + filename, 'w+')
                  file.write(str(value))
                  file.close()

                xml_attributes['content_type'] = content_type
                xml_attributes['filename']     = filename
                xml_attributes['download_url'] = brain.getURL() + '/at_download/' + field['name']

                self.createChild(item, field['name'], './files/' + filename, xml_attributes)

            elif field['type'] == 'text':
              xml_attributes['content_type'] = obj.getContentType(field['name'])
              self.createChild(item, field['name'], str(value), xml_attributes)

            elif isinstance(value, (list, tuple)):
              """
                If the value is a list or a tuple it will add the values in inner tags
              """
              xml_attributes['iterable'] = 'True'
              attribute = self.createChild(item, field['name'], None, xml_attributes)

              attr_child_tagname = field['name'] + '_item'
              if field['name'].endswith('s'):
                attr_child_tagname = field['name'][:-1]

              for attr_child_value in value:
                self.happens('Adding child ' + str(attr_child_value) + ' to field', 'sub event')

                if field['type'] == 'reference':
                  self.createChild(attribute, attr_child_tagname, attr_child_value.UID(), {'type': 'UID'})
                else: # if field['type'] == 'lines' or isinstance(attr_child_value, str):
                  self.createChild(attribute, attr_child_tagname, attr_child_value)

            else:
              self.createChild(item, field['name'], str(value), xml_attributes)

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
    self.metadata_file =  open(self.output_folder + '/metadata.json', 'w+')

    self.log_file.close()
    self.xml_file.close()
    self.metadata_file.close()


  def research_fields(self):
    self.contenttype_metadata['fields'] = self.research_fields_by_schema(self.contenttype_metadata['schema'])


  def research_fields_by_schema(self, schema = None):
    output = []
    for field_instance in schema.fields():
      if field_instance.getName() != 'id':
        field = self.parse_field(field_instance)
        output.append(field)
        self.happens('Added field width data: ' + str(field), 'sub_event')

    return output


  def parse_field(self, field_instance):
    field = {
      'name':     field_instance.getName(),
      'type':     field_instance._properties['type'],
      'accessor': field_instance.accessor,
      'mutator':  field_instance.mutator,
      'instance': field_instance
    }

    if not field['accessor']:
      field['accessor'] = 'get' + field['name'][0].upper() + field['name'][1:]

    if not field['mutator']:
      field['mutator'] = 'set' + field['name'][0].upper() + field['name'][1:]

    return field


  def createChild(self, parent, tag_name, value = None, attributes = None, value_node_method = 'createTextNode'):
    child = self.doc.createElement(tag_name)

    if value:
      text = getattr(self.doc, value_node_method)(value)
      child.appendChild(text)

    if attributes:
      for attr in attributes:
        child.setAttribute(attr, attributes[attr])

    parent.appendChild(child)
    return child


  def happens(self, msg, log_type = 'event', new_line = True):
    if log_type in self.log_shows:
      log_file = open(self.log_file.name, 'a')
      output = self.test(new_line,'\n' + datetime.now().strftime('%H:%M:%S') + ' -- ' + str(msg), str(msg))
      sys.stdout.write(output)
      sys.stdout.flush()
      log_file.write(output)
      log_file.close()


