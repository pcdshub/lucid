import versioneer
from setuptools import (setup, find_packages)


with open('requirements.txt') as f:
    requirements = f.read().split()

git_requirements = [r for r in requirements if r.startswith('git+')]
requirements = [r for r in requirements if not r.startswith('git+')]
print("User must install the following packages manually:\n" +
      "\n".join(f' {r}' for r in git_requirements))

setup(name='lucid',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      license='BSD-like',
      author='SLAC National Accelerator Laboratory',
      install_requires=requirements,
      packages=find_packages(),
      description='LCLS User Controls and Inteface Design',
      include_package_data=True,
      entry_points={
          'gui_scripts': [
              'lucid=lucid.launcher:main'
          ]
      }
      )
