"""Data Manager Metadata Class Definitions.
    Hints: https://pynative.com/make-python-class-json-serializable/
"""
import json
import datetime
import yaml
import copy
from abc import ABC, abstractmethod

_METADATA_VERSION: str = '0.0.1'
_ANNOTATION_VERSION: str = '0.0.1'
_SCHEMA: str = 'http://json-schema.org/draft/2019-09/schema#'
_SCHEMA_ID: str = 'https://example.com/product.schema.json'

# This is the basic structure of the rows FieldsDescriptorAnnotation Properties list
# That is indexed by the property name.
PROPERTY_DICT = {'type': '', 'description': '', 'required': False,
                  'active': False}

def metadata_version() -> str:
    return _METADATA_VERSION


def annotation_version() -> str:
    return _ANNOTATION_VERSION


class Metadata:
    """Class Metadata

    Purpose: Defines a list of metadata dnd annotations that can be serialized and saved in a
    dataset.

    """
    dataset_name: str = ''
    dataset_uuid: str = ''
    description: str = ''
    created: datetime = 0
    last_updated: datetime = 0
    created_by: str = ''
    metadata_version: str = ''
    annotations: list = []

    def __init__(self, dataset_name: str, dataset_uuid: str, description: str,
                 created_by: str):
        assert dataset_name
        assert dataset_uuid
        assert created_by

        self.dataset_name = dataset_name
        self.dataset_uuid = dataset_uuid
        self.description = description
        self.created = datetime.datetime.utcnow()
        self.last_updated = self.created
        self.created_by = created_by
        self.metadata_version = metadata_version()
        self.annotations = []

    def get_dataset_name(self):
        return self.dataset_name

    def set_dataset_name(self, dataset_name: str):
        assert dataset_name
        annotation = PropertyChangeAnnotation('dataset_name', self.dataset_name)
        self.add_annotation(annotation)
        self.dataset_name = dataset_name

    def get_dataset_uuid(self):
        return self.dataset_uuid

    def set_dataset_uuid(self, dataset_uuid: str):
        assert dataset_uuid
        annotation = PropertyChangeAnnotation('dataset_uuid', self.dataset_uuid)
        self.add_annotation(annotation)
        self.dataset_uuid = dataset_uuid

    def get_description(self):
        return self.description

    def set_description(self, description: str):
        annotation = PropertyChangeAnnotation('description', self.description)
        self.add_annotation(annotation)
        self.description = description

    def get_created_by(self):
        return self.created_by

    def set_created_by(self, created_by: str):
        assert created_by
        annotation = PropertyChangeAnnotation('created_by', self.created_by)
        self.add_annotation(annotation)
        self.created_by = created_by

    def get_metadata_version(self):
        return self.metadata_version

    def get_annotation(self, pos: int):
        """ Get an annotation from the annotation list identified by the position.
        """
        return self.annotations[pos]

    def add_annotation(self, annotation: object):
        """ Add a serialized annotation to the annotation list
        """
        self.annotations.append(annotation)
        self.last_updated = datetime.datetime.utcnow()

    def get_annotations_dict(self, annotation_type=all):
        """ Get a list of all annotations from the annotation list in dict format.

            The list can be filtered by annotation class.
            Within an annotation class, the keyword arguments can be used to filter within
            a particular class.
        """
        anno_list = []
        for anno in self.annotations:
            if annotation_type is all:
                anno_list.append(anno.to_dict())
            elif anno.get_type() is annotation_type:
                anno_list.append(anno.to_dict())
        return anno_list

    def get_annotations_json(self, annotation_type=all):
        """ Get a list of all annotations from the annotation list in json format.
        """
        return json.dumps(self.get_annotations_dict(annotation_type))

    def _create_annotation(self, annotation_row: dict):
        """ Creates an annotation object based on the dictionary and add to the annotations list.
        """
        class_lookup = {'PropertyChangeAnnotation': PropertyChangeAnnotation,
                        'LabelAnnotation': LabelAnnotation,
                        'FieldsDescriptorAnnotation': FieldsDescriptorAnnotation,
                        'ServiceExecutionAnnotation': ServiceExecutionAnnotation}

        # Get class and original create data
        annotation_class = annotation_row['type']
        annotation_created = annotation_row['created']

        # Remove from parameter list
        del annotation_row['type']
        del annotation_row['created']
        del annotation_row['annotation_version']

        # Create new annotation for metadata using rest of original parameters
        # and reset created datetime. This also effectively validates the content.
        annotation = class_lookup[annotation_class](**annotation_row)
        annotation.set_created(annotation_created)
        self.add_annotation(annotation)

    def add_annotations(self, annotations: json):
        """ Add a list of annotations in json format to the annotation list
        """
        # Note that this also validates the Json and returns a ValueError if not valid
        annotations_list = json.loads(annotations)

        # If a single annotation is provided but it's simply not in a list then add it
        if annotations.lstrip()[0] != '[':
            annotations_list = []
            annotations_list.append(json.loads(annotations))

        for annotation_row in annotations_list:
            self._create_annotation(annotation_row)
        self.last_updated = datetime.datetime.utcnow()

    def get_json_schema(self):
        """ Returns the latest complete FieldsDescriptor as a dict of the json schema
            as defined in https://json-schema.org/.
        """

        # Process all FieldDescriptor Annotations in the Annotations list in order
        # to retrieve all of the properties in the dataset. Add these to a single
        # new FieldDescriptor that will have compilation of all properties.
        # We can then extract the active properties from the final compiled FieldDescriptor to
        # use in the json schema output.
        comp_descriptor = FieldsDescriptorAnnotation()
        for annotation in self.annotations:
            if annotation.get_type() == 'FieldsDescriptorAnnotation':
                comp_descriptor.add_properties(annotation.get_properties())
        properties = {}
        required = []

        for prop, value in comp_descriptor.get_properties(False).items():
            properties[prop] = {'type': value['type'], 'description': value['description']}
            if value['required']:
                required.append(prop)

        schema = {'$schema': _SCHEMA,
                  '$id': _SCHEMA_ID,
                  'title': self.dataset_name,
                  'description': self.description,
                  "type": "object",
                  'properties': properties,
                  'required': required}

        return schema

    def get_labels(self, active=None):
        """ Returns a list of the active/inactive Label Annotations.
            The last version of each label is returned.
            If the last entry of the label annotation is marked as inactive then
            the label is not returned in the list.
        """
        label_list = []
        label_set = set()
        # Read through labels in reverse order and take the latest one for each label.
        for anno in reversed(self.annotations):
            if anno.get_type() == 'LabelAnnotation' and (anno.get_label() not in label_set):
                label_list.append(anno)
                label_set.add(anno.get_label())

        # If not active then filter any inactive labels
        if active is True:
            for label in label_list:
                if label.get_active() is False:
                    label_list.remove(label)

        if active is False:
            for label in label_list:
                if label.get_active() is True:
                    label_list.remove(label)

        return [label.to_dict() for label in label_list]

    def to_dict(self):
        """Return principle data items in the form of a dictionary
        """
        return {"dataset_name": self.dataset_name,
                "dataset_id": self.dataset_uuid,
                "description": self.description,
                "created": self.created.isoformat(),
                "last_updated": self.last_updated.isoformat(),
                "created_by": self.created_by,
                "metadata_version": self.metadata_version,
                "annotations": [anno.to_dict() for anno in self.annotations]}

    def to_json(self):
        """ Serialize class to JSON
        """
        output_dict = self.to_dict()
        return json.dumps(output_dict)


class Annotation(ABC):
    """Class Annotation - Abstract Base Class to enable annotation functionality

    Purpose: Annotations can be added to Metadata. They are defined as classes to that they can
    have both fixed data and methods that work with the data.

    """
    created: datetime = 0
    annotation_version: str = ''

    @abstractmethod
    def __init__(self):
        self.created = datetime.datetime.utcnow()
        self.annotation_version = annotation_version()

    def get_type(self):
        return self.__class__.__name__

    def set_created(self, created):
        """This used only when transferring existing annotations to a new metadata instance.
        """
        self.created = datetime.datetime.fromisoformat(created)

    def to_dict(self):
        """Return principle data items in the form of a dictionary
        """
        return {"type": self.__class__.__name__,
                "created": self.created.isoformat(),
                "annotation_version": self.annotation_version}

    def to_json(self):
        """ Serialize class to JSON
        """
        return json.dumps(self.to_dict())


class PropertyChangeAnnotation(Annotation):
    """Class PropertyChangeAnnotation

    Purpose: A simple annotation used when a property changes in the metadata.

    """
    meta_property: str = ''
    previous_value: str = ''

    def __init__(self, meta_property: str, previous_value: str):
        assert property
        self.meta_property = meta_property
        self.previous_value = previous_value
        super().__init__()

    def to_dict(self):
        """Return principle data items in the form of a dictionary
        """
        output_dict = {"meta_property": self.meta_property,
                       "previous_value": self.previous_value}
        return {**super().to_dict(), **output_dict}


class LabelAnnotation(Annotation):
    """Class LabelAnnotation

    Purpose: Object to create a simple label type of annotation to add to the metadata.

    """
    label: str = ''
    value: str = ''
    active: bool = True

    def __init__(self, label: str, value: str = '', active: bool = True):
        assert label
        self.label = label
        self.value = value
        self.active = active
        super().__init__()

    def get_label(self):
        return self.label

    def get_value(self):
        return self.value

    def get_active(self):
        return self.active

    def to_dict(self):
        """Return principle data items in the form of a dictionary
        """
        return {**super().to_dict(),
                "label": self.label,
                "value": self.value,
                "active": self.active}


class FieldsDescriptorAnnotation(Annotation):
    """Class FieldsDescriptorAnnotation

    Purpose: Object to add a Fields Descriptor annotation to the metadata.
    The class contains a list of properties that a dataset will contain.
    This is expected to be of the format:
    { "name": string, "type": string, "description": string, "active": boolean}

    """
    origin: str = ''
    description: str = ''
    properties: dict = {}

    def __init__(self, origin: str = '', description: str = '', properties: dict = None):
        self.origin = origin
        self.description = description
        if properties:
            self.add_properties(properties)
        else:
            self.properties = {}
        super().__init__()

    def get_origin(self):
        return self.origin

    def set_origin(self, origin):
        self.origin = origin

    def get_description(self):
        return self.description

    def set_description(self, description):
        self.description = description

    def add_property(self, prop_name: str,
                     active: bool = True,
                     prop_type: str = None,
                     description: str = None,
                     required: bool = None):
        """ Add an individual property to the properties list
        """
        assert prop_name
        if prop_name not in self.properties:
            # Note that this has to be copied in or it will reference the same dict.
            self.properties[prop_name] = copy.deepcopy(PROPERTY_DICT)

        self.properties[prop_name]['active'] = active
        if prop_type:
            self.properties[prop_name]['type'] = prop_type
        if description:
            self.properties[prop_name]['description'] = description
        if required:
            self.properties[prop_name]['required'] = required

    def get_property(self, prop_name: str):
        """ Get a property from the properties list identified by the name.
        """
        return self.properties[prop_name]

    def add_properties(self, new_properties: dict):
        """ Add a dictionary of additions/updates to the properties list
            properties.
        """

        for prop, values in new_properties.items():
            # unpack the individual lines for processing, adding optional fields.
            if 'description' not in values.keys():
                values['description'] = ''
            if 'required' not in values.keys():
                values['required'] = False

            self.add_property(prop, values['active'], values['type'],
                              values['description'], values['required'])

    def get_properties(self, get_all:bool = False):
        """ Get (all/only active) properties from the property list in dict format.
        """
        if get_all:
            return self.properties
        else:
            # Return active properties only
            active_properties = {}
            for prop, value in self.properties.items():
                if value['active']:
                    active_properties[prop]=value
            return active_properties

    def to_dict(self):
        """Return principle data items in the form of a dictionary
        """
        return {**super().to_dict(), "origin": self.origin,
                "description": self.description, "properties": self.properties}


class ServiceExecutionAnnotation(FieldsDescriptorAnnotation):
    """Class FieldAnnotation

    Purpose: Object to add a Field Descriptor annotation to the metadata.

    """
    service: str = ''
    service_version: str = ''
    service_user: str = ''
    service_description: str = ''
    service_ref: str = ''
    service_parameters: dict = {}

    def __init__(self, service: str,
                 service_version: str,
                 service_user: str,
                 service_description : str,
                 service_ref: str,
                 service_parameters: dict = None,
                 origin: str = '',
                 description: str = '',
                 properties: list = None):

        assert service
        assert service_version
        assert service_user
        assert service_description
        assert service_ref
        self.service = service
        self.service_version = service_version
        self.service_user = service_user
        self.service_description = service_description
        self.service_ref = service_ref
        if service_parameters:
            self.service_parameters = copy.deepcopy(service_parameters)
        else:
            self.service_parameters = {}
        super().__init__(origin, description, properties)

    def get_service(self):
        return self.service

    def set_service(self, service: str):
        assert service
        self.service = service

    def get_service_version(self):
        return self.service_version

    def set_service_version(self, service_version: str):
        self.service_version = service_version

    def get_service_user(self):
        return self.service_user

    def set_service_user(self, service_user: str):
        self.service_user = service_user

    def get_service_parameters(self):
        return self.service_parameters

    def set_service_parameters(self, service_parameters: dict):
        self.service_parameters = copy.deepcopy(service_parameters)

    def parameters_to_yaml(self):
        return yaml.dump(self.service_parameters)

    def to_dict(self):
        """Return principle data items in the form of a dictionary
        """
        return {**super().to_dict(),
                "service": self.service, "service_version": self.service_version,
                "service_user": self.service_user,
                "service_description": self.service_description,
                "service_ref": self.service_ref,
                "service_parameters": self.service_parameters}


if __name__ == "__main__":
    print('Data Manager Metadata (v%s)', _METADATA_VERSION)
    print('Data Manager Annotation (v%s)', _ANNOTATION_VERSION)
