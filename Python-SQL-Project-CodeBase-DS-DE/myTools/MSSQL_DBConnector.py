import platform

from myTools import DBConnector as db
import myTools.ModuleInstaller as mi

try:
    import pyodbc
except:
    mi.installModule("pyodbc")
    import pyodbc


class MSSQL_DBConnector(db.DBConnector):
    """This class inherits from the abstract class _DBConnector and implements _selectBestDBDriverAvailable for a MSSQL server connection"""

    def __init__(self: object, DSN, dbserver: str, dbname: str, dbusername: str, \
                 dbpassword: str, trustedmode: bool =  False, viewname: str = "", isPasswordObfuscated:bool = True):
        
        super().__init__(DSN = DSN, dbserver = dbserver, dbname= dbname, dbusername = dbusername, \
            dbpassword = dbpassword, trustedmode = trustedmode, viewname = viewname, isPasswordObfuscated = isPasswordObfuscated)

        self._selectBestDBDriverAvailable()

    def _selectBestDBDriverAvailable(self: object) -> None:
        lstAvailableDrivers:list[str] = pyodbc.drivers()
        
        identifiedOS: str = platform.system()


        if (lstAvailableDrivers is not None):
            
            if(len(lstAvailableDrivers) > 0):
               
                if('windows' in identifiedOS.lower()):
                    #According to recommendations found here: https://github.com/mkleehammer/pyodbc/wiki/Connecting-to-SQL-Server-from-Windows

                    if("ODBC Driver 17 for SQL Server" in lstAvailableDrivers):
                        self._m_dbDriver = "ODBC Driver 17 for SQL Server"
                    if("ODBC Driver 13.1 for SQL Server" in lstAvailableDrivers):
                        self._m_dbDriver = "ODBC Driver 13.1 for SQL Server"
                    if("ODBC Driver 13 for SQL Server" in lstAvailableDrivers):
                        self._m_dbDriver = "ODBC Driver 13 for SQL Server"
                    if("ODBC Driver 11 for SQL Server" in lstAvailableDrivers):
                        self._m_dbDriver = "ODBC Driver 11 for SQL Server"

                if(self.selectedDriver == 'undef'):
                    raise Exception('no suitable DB drivers found on the system')

            else:
                raise Exception('pyobdc cannot find any DB drivers installed on the system')
        else:
            raise Exception('pyodbc fails to extract the DB drivers installed on the system')


