import re
import os
import platform
from .log import PypeLogger

log = PypeLogger().get_logger(__name__)

platform = platform.system().lower()


class _Dict_to_obj_with_range(dict):
    """
    Converts `dict` dot string object with optional slicing method

    Output:
        nested dotstring object for example: root.item.subitem.subitem_item
        also nested dict() for example: root["item"].subitem["subitem_item"]

    Arguments:
        dict (dictionary): nested dictionary
        range (list): list of list pairs example:
        (key, list of two int())
    """
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def __init__(self, dct, range=None):
        for key, value in dct.items():
            if isinstance(value, dict):
                value = _Dict_to_obj_with_range(value, range)

            try:
                cut_from, cut_to = [found[1]
                                    for found in range
                                    if key in found[0]][0]
                self[key] = value[cut_from:cut_to]
            except Exception:
                self[key] = value


def _solve_optional(template, data):
    """
    Solving optional elements in template string regarding to available
    keys in used data object

    Arguments:
        template (string): value from toml templates
        data (obj): containing keys to be filled into template
    """
    # print(template)
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

    try:
        solved = template.format(**data)

        # solving after format optional in second round
        for catch in re.compile(r"(<.*?[^{0]*>)[^0-9]*?").findall(solved):
            if "{" in catch:
                # remove all optional
                solved = solved.replace(catch, "")
            else:
                # Remove optional symbols
                solved = solved.replace(catch, catch[1:-1])

        return solved
    except KeyError as e:
        log.debug("_solve_optional: {},"
                  "`template`: {}".format(e, template))
        return template
    except ValueError as e:
        log.error("Error in _solve_optional: {},"
                  "`template`: {}".format(e, template))


def _slicing(template):
    """ Hiden metod

    finds slicing string in `template` and remove it and returns pair list
    with found 'key' and [range]

    Arguments:
        template (string): value from toml templates
        data (directory): containing keys to be filled into template


    """
    pairs = []
    # patterns
    sliced_key = re.compile(r"^.*{(.*\[.*?\])}")
    slice_only = re.compile(r"\[.*?\]")

    # procedure
    find_sliced = sliced_key.findall(template)
    for i, sliced in enumerate(find_sliced):
        slicing = slice_only.findall(sliced)
        try:
            numbers_get = [
                int(n) for n in slicing[i].replace(
                    "[", ""
                ).replace(
                    "]", ""
                ).split(":")
            ]
            clean_key = sliced.replace(slicing[i], "")
            template = template.replace(slicing[i], "")
            pairs.append((clean_key, numbers_get))
        except ValueError as e:
            pairs.append(None)
            log.debug("formating._slicing: {}".format(e))
    return template, pairs


def format(template="{template_string}", data=dict()):
    """ Public metod

    Converts `template` string and returns corrected string

    Arguments:
        template (string): value from toml templates
        data (directory): containing keys to be filled into template
    """
    template, range = _slicing(template)

    converted = _solve_optional(
        template,
        _Dict_to_obj_with_range(
            dict(data, **os.environ),
            range
        )
    )

    return converted