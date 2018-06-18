from setuptools import setup

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    name='coinmarketcap_tracker',
    version='0.1dev14',
    author='Hunter M. Allen',
    author_email='allenhm@gmail.com',
    license='MIT',
    #packages=find_packages(),
    packages=['coinmarketcap_tracker'],
    #scripts=['bin/heartbeatmonitor.py'],
    install_requires=['slackclient>=1.2.1',
                      'heartbeatmonitor>=0.1a23'],
    description='Tracks Coinmarketcap data for selected cryptocurrency products over time and sends Slack alerts.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/hmallen/coinmarketcap_tracker',
    keywords=['coinmarketcap', 'tracker', 'slack'],
    classifiers=(
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ),
)
