"""Built-in skin selection; catalogs never inherit another character's art."""
import os

SKINS = ('yukio', 'qianxia')


def normalize_skin(value):
    return value if value in SKINS else 'yukio'


def skin_root(root, skin):
    if skin not in SKINS:
        raise ValueError('Unknown skin: %s' % skin)
    return root if skin == 'yukio' else os.path.join(root, 'skins', skin)
