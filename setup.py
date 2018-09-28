import versioneer
from setuptools import (setup, find_packages)


setup(name     = 'lucid',
      version  = versioneer.get_version(),
      cmdclass = versioneer.get_cmdclass(),
      license  = 'BSD-like',
      author   = 'SLAC National Accelerator Laboratory',
      packages    = find_packages(),
      description = 'LCLS User Controls and Inteface Design',
      include_package_data = True,
    )
