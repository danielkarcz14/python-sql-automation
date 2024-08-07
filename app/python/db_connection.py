import pyodbc
import configparser
import os

def db_connection():
    # Napojení na databázi
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config", "configfile.ini")
    config_obj = configparser.ConfigParser()
    config_obj.read(config_path)
    dbparam = config_obj["login"]

    server = dbparam["server"]
    database = dbparam["database"]
    username = dbparam["username"]
    password = dbparam["password"]

    try:
        conn = pyodbc.connect('DRIVER={/opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.3.so.2.1};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+ password + ';LOGIN_TIMEOUT=60')
        cur = conn.cursor()
        user = conn.getinfo(pyodbc.SQL_USER_NAME)
        return conn, cur, user
    except pyodbc.Error as e:
        print(f"Nepodařilo se připojit k db {e}")
        return None
    
