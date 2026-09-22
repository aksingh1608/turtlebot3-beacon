from glob import glob

from setuptools import setup

package_name = 'beacon'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/worlds', glob('worlds/*.world')),
        ('share/' + package_name + '/models/red_marker', glob('models/red_marker/*')),
        ('share/' + package_name + '/config', glob('config/*')),
        ('share/' + package_name + '/trials', ['trials/positions.csv']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AK Singh',
    maintainer_email='aksingh5114@gmail.com',
    description='Vision guided TurtleBot3 marker search and approach in Gazebo.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'detector_node = beacon.detector_node:main',
            'controller_node = beacon.controller_node:main',
            'trial_logger_node = beacon.trial_logger_node:main',
            'spawn_marker = beacon.spawn_marker:main',
        ],
    },
)
