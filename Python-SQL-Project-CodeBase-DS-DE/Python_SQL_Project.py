import argparse as agp
import getpass
import os

from myTools import MSSQL_DBConnector as mssql
from myTools import DBConnector as dbc
import myTools.ContentObfuscation as ce


try:
    import pandas as pd
except:
    mi.installModule("pandas")
    import pandas as pd



def printSplashScreen():
    print("*************************************************************************************************")
    print("\t THIS SCRIPT ALLOWS TO EXTRACT SURVEY DATA FROM THE SAMPLE SEEN IN SQL CLASS")
    print("\t IT REPLICATES THE BEHAVIOUR OF A STORED PROCEDURE & TRIGGER IN A PROGRAMMATIC WAY")
    print("\t COMMAND LINE OPTIONS ARE:")
    print("\t\t -h or --help: print the help content on the console")
    print("*************************************************************************************************\n\n")



def processCLIArguments()-> dict:
    """This function enables user to pass parameters through the command line"""

    retParametersDictionary:dict = None
    
    dbpassword:str = ''
    obfuscator: ce.ContentObfuscation = ce.ContentObfuscation()

    try:
        argParser:agp.ArgumentParser = agp.ArgumentParser(add_help=True)

        argParser.add_argument("-n", "--DSN", dest="dsn", \
                                action='store', default= None, help="Sets the SQL Server DSN descriptor file - Take precedence over all access parameters", type=str)
        argParser.add_argument("-s", "--DBServer", dest="dbserver", \
                                action='store', default= None, help="Sets the SQL Server Server Name", type=str)
        argParser.add_argument("-d", "--DBName", dest="dbname", \
                                action='store', default= None, help="Sets the database name", type=str)
        argParser.add_argument("-u", "--DBUserName", dest="dbusername", \
                                action='store', default= None, help="Sets login for SQL Server Authentication", type=str)
        argParser.add_argument("-p", "--DBUserPassword", dest="dbuserpassword", \
                                action='store', default= None, help="Sets password for SQL Server Authentication", type=str)
        argParser.add_argument("-t", "--TrustedMode", dest="trustedmode", \
                                action='store', default= False, help="Sets the trusted mode", type=bool)
        argParser.add_argument("-v", "--ViewName", dest="viewname", \
                                action='store', default= None, help="Sets the view name", type=str)
        argParser.add_argument("-f", "--PersistenceFilePath", dest="persistencefilepath", \
                                action='store', help="Sets the file path for the persistene log", type=str)
        argParser.add_argument("-r", "--ResultsFilePath", dest="resultsfilepath", \
                                action='store', help="Sets the file path for the results", type=str)
        argParsingResults = argParser.parse_args()

        if (argParsingResults.dbuserpassword != None):
            #obfuscate the password if inputed
            dbpassword = obfuscator.obfuscate(argParsingResults.dbuserpassword)

        retParametersDictionary = {
                    "dsn" : argParsingResults.dsn,        
                    "dbserver" : argParsingResults.dbserver,
                    "dbname" : argParsingResults.dbname,
                    "dbusername" : argParsingResults.dbusername,
                    "dbuserpassword" : dbpassword,
                    "trustedmode" : argParsingResults.trustedmode,
                    "viewname" : argParsingResults.viewname,
                    "persistencefilepath": argParsingResults.persistencefilepath,
                    "resultsfilepath" : argParsingResults.resultsfilepath
                }

    except Exception as e:
        print("Command Line arguments processing error: " + str(e))

    return retParametersDictionary


def getSurveyStructure(connector: mssql.MSSQL_DBConnector) -> pd.DataFrame:
    """Gets the SurveyStructure from the connetced database as pandas dataframe"""
    surveyStructResults = None
    strSurveyStructure = 'SELECT * FROM SurveyStructure'
    surveyStructResults = connector.ExecuteQuery_withRS(strSurveyStructure)
    return surveyStructResults



def doesPersistenceFileExist(persistenceFilePath: str)-> bool:
    """Checks if the persistence file already exits"""
    success = os.path.isfile(persistenceFilePath)

    return success



def isPersistenceFileDirectoryWritable(persistenceFilePath: str)-> bool:
    """Checks if the directory of the persistence file is writable"""
    success = os.access(os.path.dirname(persistenceFilePath), os.W_OK)
    return success


def compareDBSurveyStructureToPersistenceFile(surveyStructResults:pd.DataFrame, persistenceFilePath: str) -> bool:
    """Compares current SurveyStructure in the database vs. SurveyStructure saved in the persistence file"""
    same_file = False
    persistenceDF = pd.read_csv(persistenceFilePath)
    same_file = surveyStructResults.equals(persistenceDF)

    return same_file



def getAllSurveyDataQuery(connector: dbc.DBConnector) -> str:
    """Generates query str getAllSurveyData => Conversion of code of getAllSurveyData written in T-SQL """

    strQueryTemplateForAnswerColumn: str = """COALESCE( 
				( 
					SELECT a.Answer_Value 
					FROM Answer as a 
					WHERE 
						a.UserId = u.UserId 
						AND a.SurveyId = <SURVEY_ID> 
						AND a.QuestionId = <QUESTION_ID> 
				), -1) AS ANS_Q<QUESTION_ID> """ 


    strQueryTemplateForNullColumnn: str = ' NULL AS ANS_Q<QUESTION_ID> '

    strQueryTemplateOuterUnionQuery: str = """ 
			SELECT 
					UserId 
					, <SURVEY_ID> as SurveyId 
					, <DYNAMIC_QUESTION_ANSWERS> 
			FROM 
				[User] as u 
			WHERE EXISTS 
			( \
					SELECT * 
					FROM Answer as a 
					WHERE u.UserId = a.UserId 
					AND a.SurveyId = <SURVEY_ID> 
			) 
	"""

    strCurrentUnionQueryBlock: str = ''

    strFinalQuery: str = ''

    # Cursors are replaced by a query retrived in a pandas df
    surveyQuery:str = 'SELECT SurveyId FROM Survey ORDER BY SurveyId' 
    surveyQueryDF:pd.DataFrame = connector.ExecuteQuery_withRS(surveyQuery)

    #MAIN LOOP, OVER ALL THE SURVEYS
    for index1, row in surveyQueryDF.iterrows():
        currentSurveyId = row.SurveyId
        strCurrentQuestionQuery: str = """
                SELECT *
				FROM
					(
						SELECT
							SurveyId,
							QuestionId,
							1 as InSurvey
						FROM
							SurveyStructure
						WHERE
							SurveyId = {currentSurveyId}
						UNION
						SELECT 
							{currentSurveyId} as SurveyId,
							Q.QuestionId,
							0 as InSurvey
						FROM
							Question as Q
						WHERE NOT EXISTS
						(
							SELECT *
							FROM SurveyStructure as S
							WHERE S.SurveyId = {currentSurveyId} AND S.QuestionId = Q.QuestionId
						)
					) as t
					ORDER BY QuestionId;
        """.format(currentSurveyId = currentSurveyId)
        CurrentQuestionQueryDF = connector.ExecuteQuery_withRS(strCurrentQuestionQuery)
        strColumnsQueryPart: str = ''

        #Inner loop: for the current survey, iterate over the questions and construct the answer column queries
        for index2, row in CurrentQuestionQueryDF.iterrows():
            currentInSurvey = row.InSurvey
            currentQuestionId = row.QuestionId
            if currentInSurvey == 0:
                strColumnsQueryPart = strColumnsQueryPart + strQueryTemplateForNullColumnn.replace('<QUESTION_ID>', str(currentQuestionId))
            else:
                strColumnsQueryPart = strColumnsQueryPart + strQueryTemplateForAnswerColumn.replace('<QUESTION_ID>', str(currentQuestionId))
            if index2 != (len(CurrentQuestionQueryDF) - 1):
                strColumnsQueryPart = strColumnsQueryPart + ','

        strCurrentUnionQueryBlock = strQueryTemplateOuterUnionQuery.replace('<DYNAMIC_QUESTION_ANSWERS>', strColumnsQueryPart)

        strCurrentUnionQueryBlock = strCurrentUnionQueryBlock.replace('<SURVEY_ID>', str(currentSurveyId))

        strFinalQuery = strFinalQuery + strCurrentUnionQueryBlock

        if (index1 != len(surveyQueryDF)-1):
            strFinalQuery = strFinalQuery + ' UNION '

    return strFinalQuery



def refreshViewInDB(connector: dbc.DBConnector, baseViewQuery:str, viewName:str)->None:
    """Creates/Refreshes View in the database"""
    if(connector.IsConnected == True):
        strSQLSurveyData = 'CREATE OR ALTER VIEW {} AS '.format(viewName) + '(' + baseViewQuery + ')'
        connector.CreateRefreshView(strSQLSurveyData)
        


def surveyResultsToDF(connector: dbc.DBConnector, viewName:str)->pd.DataFrame:
    """Sends query to DB to get the View table as pandas dataframe"""
    results:pd.DataFrame = None
    strViewQuery = "SELECT * FROM {}".format(viewName)
    results = connector.ExecuteQuery_withRS(strViewQuery)
    return results


def main():
    
    cliArguments:dict = None

    printSplashScreen()

    try:
        cliArguments = processCLIArguments()
    except Except as excp:
        print("Exiting")
        return

    if(cliArguments is not None):

        try:
            #Connect to the database
            connector = mssql.MSSQL_DBConnector(DSN = cliArguments["dsn"], dbserver = cliArguments["dbserver"], \
                dbname = cliArguments["dbname"], dbusername = cliArguments["dbusername"], \
                dbpassword = cliArguments["dbuserpassword"], trustedmode = cliArguments["trustedmode"], \
                viewname = cliArguments["viewname"])
            
            connector.Open()

            surveyStructureDF:pd.DataFrame = getSurveyStructure(connector)

            baseViewQuery = getAllSurveyDataQuery(connector)

            viewName = cliArguments["viewname"]

            if(doesPersistenceFileExist(cliArguments["persistencefilepath"]) == False):

                if(isPersistenceFileDirectoryWritable(cliArguments["persistencefilepath"]) == True):
              
                    #pickle the dataframe in the path given by persistencefilepath
                    surveyStructureDF.to_csv(cliArguments["persistencefilepath"], index = False, header=True)

                    print("\nINFO - Content of SurveyStructure table pickled in " + cliArguments["persistencefilepath"] + "\n")
                    
                    #creates/refresh the view using the function written for this purpose
                    refreshViewInDB(connector, baseViewQuery, viewName)
                else:
                    print("\nINFO - persistence file directory: " + os.dirname(cliArguments["persistencefilepath"]) + " is not writable\n")
                    
            else:
                #Compare the existing pickled SurveyStructure file with surveyStructureDF
                if (compareDBSurveyStructureToPersistenceFile(surveyStructureDF, cliArguments["persistencefilepath"])== False):

                    # Update the view and persistence file when the current SurveyStructureDF and the pickled file are different
                    refreshViewInDB(connector, baseViewQuery, viewName)
                    surveyStructureDF.to_csv(cliArguments["persistencefilepath"], index = False, header=True)
                    print('\nINFO - Changes to survey strcture observed, persistence file updated, '+ viewName +' updated in database\n')
                else:
                    print("\nINFO - No changes have been made to the survey structure\n")
           
            #get survey results from the view in a dataframe and save it to a CSV file in the path given by resultsfilepath
            viewDF = surveyResultsToDF(connector, viewName)
            viewDF.to_csv(cliArguments["resultsfilepath"], index = False, header=True)
            print("\nDONE - Results exported in " + cliArguments["resultsfilepath"] + "\n")

            #close the connection to database
            connector.Close()

        except Exception as excp:
            print(excp)
    else:
        print("Inconsistency: CLI argument dictionary is None. Exiting")
        return



if __name__ == '__main__':
    main()