import subprocess
import sys, os


def __isConda()-> bool:
    """Checks if the application is running under conda envirinment"""
    is_conda = os.path.exists(os.path.join(sys.prefix, 'conda-meta'))
    return is_conda



def installModule(package):
    """Set up the install process depending on the environment"""
    packageManager = "pip"

    if __isConda() == True:
        packageManager = "conda"
     
    subprocess.run([packageManager, 'install', package])
 
    