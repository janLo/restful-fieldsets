from collections import defaultdict
from flask.ext.restful import reqparse, unpack, marshal, fields
from functools import wraps


class FieldsetMeta(type):
    def __init__(cls, what, bases, attrs):
        super().__init__(what, bases, attrs)
        cls._unbound_fields = None
        cls._metadata_cls = None

    def __call__(cls, *args, **kwargs):
        if cls._unbound_fields is None:
            fields = []
            for name in dir(cls):
                if not name.startswith('_'):
                    unbound_field = getattr(cls, name)
                    if hasattr(unbound_field, 'format') and hasattr(unbound_field, "output"):
                        fields.append((name, unbound_field))
            cls._unbound_fields = fields
        if cls._metadata_cls is None:
            bases = []
            for mro_class in cls.__mro__:
                if 'Meta' in mro_class.__dict__:
                    bases.append(mro_class.Meta)
            cls._metadata_cls = type('Meta', tuple(bases), {})
            # noinspection PyArgumentList
        return type.__call__(cls, *args, **kwargs)

    def __setattr__(cls, name, value):
        """
        Add an attribute to the class, clearing `_unbound_fields` if needed.
        """
        if name == 'Meta':
            cls._metadata_cls = None
        elif not name.startswith('_') and hasattr(value, 'format') and hasattr(value, "output"):
            cls._unbound_fields = None
        type.__setattr__(cls, name, value)

    def __delattr__(cls, name):
        """
        Remove an attribute from the class, clearing `_unbound_fields` if
        needed.
        """
        if not name.startswith('_'):
            cls._unbound_fields = None
        type.__delattr__(cls, name)


class DefaultMeta(object):
    default_fields = None
    default_embedd = None
    fields_kw = "fields"
    embedd_kw = "embedd"


class FieldsetBase(object, metaclass=FieldsetMeta):
    def __init__(self, created_fields, meta):
        self.meta = meta
        self._fields = created_fields

        self._nested = self._find_nested()
        self._nested_recursive = self._find_nested_all()
        self._fields_recursive = self._find_fields_all()

        self._default_fields = self._find_default_fields()
        self._default_embedd = self._find_default_embedd()

    def _find_nested(self):
        names = []
        for field in self._fields:
            if getattr(self._fields[field], "_optional_nested", None) or \
                    (isinstance(self._fields[field], fields.List) and
                         getattr(self._fields[field].container, "_optional_nested", None)):
                names.append(field)

        return names

    def _find_nested_all(self):
        names = []
        for name in self._nested:
            names.append(name)
            nested_field = self._fields.get(name)
            if nested_field is not None:
                if isinstance(nested_field, fields.List):
                    nested_fieldset = nested_field.container.nested_fieldset()
                else:
                    nested_fieldset = nested_field.nested_fieldset()
                if nested_fieldset is not None:
                    for nested_nest_field_name in nested_fieldset.nested_field_names:
                        names.append("%s.%s" % (name, nested_nest_field_name))
        return names

    def _find_fields_all(self):
        names = []
        for name in self._fields:
            names.append(name)
        for name in self._nested:
            nested_field = self._fields.get(name)
            if nested_field is not None:
                if isinstance(nested_field, fields.List):
                    nested_fieldset = nested_field.container.nested_fieldset()
                else:
                    nested_fieldset = nested_field.nested_fieldset()
                if nested_fieldset is not None:
                    for nested_field_name in nested_fieldset.all_field_names:
                        names.append("%s.%s" % (name, nested_field_name))
        return names

    def _find_default_fields(self):
        names = []
        if self.meta is None or self.meta.default_fields is None:
            names.extend(self._fields.keys())
        else:
            names.extend(self.meta.default_fields)
        return set(names)

    def _find_default_embedd(self):
        names = []
        if self.meta is None or self.meta.default_embedd is None:
            names.extend(self._nested)
        else:
            names.extend(self.meta.default_embedd)
        return set(names)

    @property
    def all_field_names(self):
        return self._fields_recursive

    @property
    def nested_field_names(self):
        return self._nested_recursive


class FieldSetParser(object):
    def __init__(self, possible_fields):
        self.possible_fields = set(possible_fields)

    # noinspection PyUnusedLocal
    def __call__(self, value, *args, **kwargs):
        if not isinstance(value, str):
            raise ValueError("Need a str")

        if not len(value):
            return None
        elements = set(value.split(","))
        unknown = elements.difference(self.possible_fields)
        if len(unknown):
            raise ValueError("Unknown fields: %s" % ", ".join(sorted(unknown)))

        return elements


class Fieldset(FieldsetBase):
    """This implements a base class for flask-restful fieldsets.

    It works like WTForm forms:

        class MyFieldSet(Fieldset):
            member_a = fields.String
            member_b = fields.Integer(attribute="foobar")
            ...

    You inherit from this class and defines a set of Fields. In
    your resource vou can marshall your response using this field
    ad marshalling decorator:

        class MyResource(Resource):
            @marshal_with_fieldset(MyFieldSet)
            def get(self):
                ...

    Fieldsets can be nested to represent arbitrary object hierarchies.
    The nesting can also contain lists of nested fieldsets. So you can
    provide a Thread of a discussion forum and the posts as a list of
    post fieldsets in a member of the thread fieldset. To nest fieldsets
    use the OptionalNestedField:

        class MyNestedFieldset(Fieldset):
            id_value = fields.Integer
            ...

        class MyFieldSet(Fieldset):
            plain_member = fields.String
            nested_member = OptionalNestedField(MyNestedFieldset,
                                                "id_value")
            ...

    To have Lists of Nested fields use simply the list field:

        class MyFieldSet(Fieldset):
            plain_member = fields.String
            nested_member = fields.List(
                                OptionalNestedField(MyNestedFieldset,
                                                    "id_value"))
            ...

    The marshalling configuration can be changed by the user of your
    api by selecting the fields he wants. this is done by using two
    query args:
    * fields - let the user select the fields to retrieve. If there
               are nested elements they can be specified by using a
               dot as separator. So if you have a 'user' field that
               contains a user-struct the api-user can specify to
               get the 'user.name' field.
    * embedd - let the user choose if a nested fieldset should be
               embedded or not. If a nested value is not embedded,
               a id-value will be returned. This is the 'plain_key'
               in the OptionalNestedField that is used to get a
               value from the nested object.

    Both keywords are configureable within a Meta subclass. The default
    is 'fields' and 'embedd':

        class MyFieldSet(Fieldset):
            class Meta:
                fields_kw = "myfields"
                embedd_kw = "myembedd"
            ...

    The meta can also be used to define default fields and default
    embedded fieldsets (if the user does not specify anything):

        class MyFieldSet(Fieldset):
            class Meta:
                default_fields = None
                default_embedd = None
            ...

    If no Meta is given or the defaults are set to None then all
    fields will be in in the default set. If you want to omit all
    ields by default use an empty list as default.
    """
    Meta = DefaultMeta

    def __init__(self, *args, **kwargs):
        # noinspection PyCallingNonCallable
        meta_obj = self._metadata_cls()
        # noinspection PyArgumentList,PyTypeChecker
        super().__init__(dict(self._unbound_fields), meta=meta_obj)
        self._parser = None

    def _parse_request_overrides(self):
        if self._parser is None:
            parser = reqparse.RequestParser()
            parser.add_argument(self.meta.fields_kw, type=FieldSetParser(self.all_field_names))
            parser.add_argument(self.meta.embedd_kw, type=FieldSetParser(self.nested_field_names))
            self._parser = parser
        result = self._parser.parse_args()
        return getattr(result, self.meta.fields_kw), getattr(result, self.meta.embedd_kw)

    def marshall_dict(self, selected_fields=None, selected_embed=None):
        """
        :type selected_fields: set[str]
        :type selected_embed: set[str]
        """
        result_dict = {}
        if selected_fields is None or len(selected_fields) == 0:
            selected_fields = self._default_fields

        fields_direct = selected_fields.intersection(self._fields.keys())

        if selected_embed is None or len(selected_embed) == 0:
            selected_embed = self._default_embedd

        embed_direct = selected_embed.intersection(fields_direct)

        filtered_nested = defaultdict(set)
        for nested in selected_fields - fields_direct:
            if "." not in nested:
                continue
            field, nested_field = nested.split(".", 1)
            filtered_nested[field].add(nested_field)

        filtered_embedd = defaultdict(set)
        for embed in selected_embed - embed_direct:
            if "." not in embed:
                continue
            field, nested_field = embed.split(".", 1)
            filtered_embedd[field].add(nested_field)

        for field in fields_direct:
            if field in self._nested:
                if field in embed_direct:
                    if isinstance(self._fields[field], fields.List):
                        nested_fieldset = self._fields[field].container.nested_fieldset()
                        result_dict[field] = fields.List(
                            fields.Nested(nested_fieldset.marshall_dict(filtered_nested[field],
                                                                        filtered_embedd[field]),
                                          **self._fields[field].container.nested_kwargs()))
                    else:
                        nested_fieldset = self._fields[field].nested_fieldset()
                        result_dict[field] = fields.Nested(nested_fieldset.marshall_dict(filtered_nested[field],
                                                                                         filtered_embedd[field]),
                                                           **self._fields[field].nested_kwargs())
                else:
                    result_dict[field] = self._fields[field].key_field()
            else:
                result_dict[field] = self._fields[field]

        return result_dict

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            resp = f(*args, **kwargs)
            parsed = self._parse_request_overrides()
            marshall_data = self.marshall_dict(*parsed)
            if isinstance(resp, tuple):
                data, code, headers = unpack(resp)
                return marshal(data, marshall_data), code, headers
            else:
                return marshal(resp, marshall_data)

        return wrapper

    @classmethod
    def do_marshal(cls, *args, **kwargs):
        return cls(*args, **kwargs)
