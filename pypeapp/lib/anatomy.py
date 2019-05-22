import os
import re

from . import config
try:
    import ruamel.yaml as yaml
except ImportError:
    print("yaml module wasn't found, skipping anatomy")
else:
    directory = os.path.join(
        os.environ["PYPE_ENV"], "Lib", "site-packages", "ruamel"
    )
    file_path = os.path.join(directory, "__init__.py")
    if os.path.exists(directory) and not os.path.exists(file_path):
        print(
            "{0} found but not {1}. Patching ruamel.yaml...".format(
                directory, file_path
            )
        )
        open(file_path, "a").close()

"""''.format_map() in Python 2.x"""

try:
    ''.format_map({})
except AttributeError: # Python < 3.2
    import string
    def format_map(format_string, mapping, _format=string.Formatter().vformat):
        return _format(format_string, None, mapping)
    del string

    #XXX works on CPython 2.6
    # http://stackoverflow.com/questions/2444680/how-do-i-add-my-own-custom-attributes-to-existing-built-in-python-types-like-a/2450942#2450942
    import ctypes as c

    class PyObject_HEAD(c.Structure):
        _fields_ = [
            ('HEAD', c.c_ubyte * (object.__basicsize__ -  c.sizeof(c.c_void_p))),
            ('ob_type', c.c_void_p)
        ]

    _get_dict = c.pythonapi._PyObject_GetDictPtr
    _get_dict.restype = c.POINTER(c.py_object)
    _get_dict.argtypes = [c.py_object]

    def get_dict(object):
        return _get_dict(object).contents.value

    get_dict(str)['format_map'] = format_map
else: # Python 3.2+
    def format_map(format_string, mapping):
        return format_string.format_map(mapping)


class PartialDict(dict):
    ''' Modified dict class as helper.

    If is used as input data for string formatting
    missing keys won't change in string.

    .. code-block:: python

       data = PartialDict({
            'project': 'Turtle King'
       })
       string = '{project} will raise on {date}'
       result = string.format(data)

       result >> 'Turtle King will raise on {date}'
    '''
    def __getitem__(self, item):
        out = super(PartialDict, self).__getitem__(item)
        if isinstance(out, dict):
            return '{'+item+'}'
        return out

    def __missing__(self, key):
        return '{'+key+'}'


class Anatomy:
    ''' Anatomy module help get anatomy and format anatomy with entered data.

    .. todo:: should be able to load Project specific anatomy.

    Anatomy string Example:
    ``{$APP_PATH}/{project[code]}_{task}_v{version:0>3}<_{comment}>``
    - ``$APP_PATH``: environment variable
    - ``project[code]``: dictionary
    fill ``{'project':{'code': 'PROJECT_CODE'}}``
    - task, version: basic string format ``'TASK_NAME', 1``
    - comment: optional key, if not entered ``'<_{comment}>'`` will be removed

    :param project_name: Project name to look on project's anatomy overrides.
    :type project_name: str
    '''
    _anatomy = None

    def __init__(self, project=None):
        if not project:
            project = os.environ.get('AVALON_PROJECT', None)
        self.project_name = project

    @property
    def templates(self):
        if self._anatomy is None:
            self._anatomy = self._discover()
        return self._anatomy

    def _discover(self):
        ''' Loads anatomy from yaml.
        Default anatomy is loaded all the time.
        TODO: if project_name is set also tries to find project's
        anatomy overrides.

        :rtype: dictionary
        '''
        # TODO: right way to get templates path
        path = r'{PYPE_ROOT}\repos\pype-config\anatomy\default.yaml'
        path = os.path.normpath(path.format(**os.environ))
        with open(path, 'r') as stream:
            try:
                anatomy = yaml.load(stream, Loader=yaml.loader.Loader)
            except yaml.YAMLError as exc:
                print(exc)

        if self.project_name is not None:
            project_configs_path = os.path.normpath(
                os.environ.get('PYPE_PROJECT_CONFIGS', "")
            )
            project_config_items = [
                project_configs_path, self.project_name, 'anatomy', 'default.yaml'
            ]
            project_anatomy_path = os.path.sep.join(project_config_items)
            proj_anatomy = {}
            if os.path.exists(project_anatomy_path):
                with open(project_anatomy_path, 'r') as stream:
                    try:
                        proj_anatomy = yaml.load(
                            stream, Loader=yaml.loader.Loader
                        )
                    except yaml.YAMLError as exc:
                        print(exc)
            anatomy = config.update_dict(anatomy, proj_anatomy)
        return anatomy

    def _solve_with_optional(self, template, data):
        """
        Solving optional elements in template string regarding to available
        keys in used data object.

        :param template: Anatomy template which will be formatted.
        :type template: str
        :param data: Containing keys to be filled into template.
        :type data: PartialDict
        :rtype: str
        """

        # Remove optional missing keys
        pattern = re.compile(r"(<.*?[^{0]*>)[^0-9]*?")
        invalid_optionals = []
        for group in pattern.findall(template):
            try:
                group.format(**data)
            except KeyError:
                invalid_optionals.append(group)
        for group in invalid_optionals:
            template = template.replace(group, "")

        solved = format_map(template, data)

        # solving after format optional in second round
        for catch in re.compile(r"(<.*?[^{0]*>)[^0-9]*?").findall(solved):
            if "{" in catch:
                # remove all optional
                solved = solved.replace(catch, "")
            else:
                # Remove optional symbols
                solved = solved.replace(catch, catch[1:-1])

        return solved

    def _format(self, template, data):
        ''' Figure out with whole formatting.
        Separate advanced keys (*Like '{project[name]}') from string which must
        be formatted separatelly in case of missing or incomplete keys in data.

        :param template: Anatomy template which will be formatted.
        :type template: str
        :param data: Containing keys to be filled into template.
        :type data: dict
        :rtype: str
        '''

        partial_data = PartialDict(data)

        # remove subdict items from string (like 'project[name]')
        subdict = PartialDict()
        count = 1
        store_pattern = 5*'_'+'{:0>3}'
        regex_patern = "\{\w*\[[^\}]*\]\}"
        matches = re.findall(regex_patern, template)

        for match in matches:
            key = store_pattern.format(count)
            subdict[key] = match
            template = template.replace(match, '{'+key+'}')
            count += 1
        # solve fillind keys with optional keys
        solved = self._solve_with_optional(template, partial_data)
        # try to solve subdict and replace them back to string
        for k, v in subdict.items():
            try:
                v = format_map(v,data)
            except (KeyError, TypeError):
                pass
            subdict[k] = v

        return format_map(solved, subdict)

    def solve_dict(self, input, data, only_keys=True):
        ''' Solves anatomy and split results into:
        - :'solved': Fully solved anatomy strings (missing environs don't
        affect result if `only_keys` is `True`).
        - :'partial': At least one key was filled but still remain keys to fill.
        - :'unsolved': Nothing has changed in these strings.

        :param input: All Anatomy templates which will be formatted.
        :type input: dict
        :param data: Containing keys to be filled into template.
        :type data: dict
        :param only_keys: Decides if environ will be used to fill anatomy
                          or only keys in data.
        :type only_keys: bool
        :rtype: dictionary
        '''
        check_regex_keys = '\{[^\}]*\}'
        check_regex_env = '\{\$[^\}]*\}'
        output = {
            'solved': {},
            'partial': {},
            'unsolved': {}
        }

        for key, orig_value in input.items():
            if isinstance(orig_value, dict):
                for s_key, s_value in self.solve_dict(
                    orig_value, data, only_keys
                ).items():
                    for sk_key, sk_value in s_value.items():
                        if not isinstance(output[s_key], dict):
                            output[s_key] = {}
                        if key not in output[s_key]:
                            output[s_key][key] = {}

                        output[s_key][key].update({sk_key:sk_value})

            else:
                value = self._format(orig_value, data)
                solved = True
                matches = re.findall(check_regex_keys, value)
                if only_keys is True:
                    for match in matches:
                        if len(re.findall(check_regex_env, match)) == 0:
                            solved = False
                            break
                else:
                    if len(matches) > 0:
                        solved = False
                if solved is True:
                    output['solved'][key] = value
                elif orig_value==value:
                    output['unsolved'][key] = value
                else:
                    output['partial'][key] = value

        return output

    def format_all(self, data, only_keys=True):
        ''' Solves anatomy based on entered data.
        :param data: Containing keys to be filled into template.
        :type data: dict
        :param only_keys: Decides if environ will be used to fill anatomy
        or only keys in data.
        :type only_keys: bool
        :rtype: dictionary
        Returnes dictionary split into 3 categories: solved/partial/unsolved
        '''
        if only_keys is False:
            for k, v in os.environ.items():
                data['$'+k] = v
        return self.solve_dict(self.templates, data, only_keys)

    def format(self, data, only_keys=True):
        ''' Solves anatomy based on entered data.
        :param data: Containing keys to be filled into template.
        :type data: dict
        :param only_keys: Decides if environ will be used to fill anatomy
        or only keys in data.
        :type only_keys: bool
        :rtype: dictionary
        Returnes only solved
        '''
        return self.format_all(data, only_keys)['solved']