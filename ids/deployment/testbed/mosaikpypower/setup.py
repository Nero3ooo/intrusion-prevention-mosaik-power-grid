from setuptools import setup, find_packages


setup(
    name='mosaik-pypower',
    version='0.8.0',
    author='Stefan Scherfke',
    author_email='mosaik@offis.de',
    description='An adapter to use PYPOWER with mosaik.',
    long_description=(open('README.md').read()),
    url='https://gitlab.com/mosaik/mosaik-pypower',
    install_requires=[
        'PYPOWER>=4.1,<=5.1.15',
        'mosaik-api>=3.0',
        'numpy>=1.6',
        'scipy>=0.9,<=1.6.3',
        'xlrd>=0.9.2,<=2.0.1',
    ],
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'mosaik-pypower = mosaik_pypower.mosaik:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Scientific/Engineering',
    ],
)
