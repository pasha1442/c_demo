AI Solutions


Step 1 -  install postgres

sudo apt install postgresql postgresql-contrib

Step 2 - Configure postgres

sudo -u postgres psql
create user username with password 'password'
create database db_name owner username;
grant all privileges on database db_name to username;

Step 3 - Dump database 
psql -h localhost -p 5432 -U username -d db_name -f filename.sql 

Step 3 - In .env

DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=
SECRET_KEY=""
OPEN_AI_KEY=""
KL_TOKEN=

-------------------------------------------------------------
- Configuring Guardrails 
  Commands: "guardrails configure"
  pip install guardrails-ai

- guardrails configure
- guardrails hub install hub://guardrails/profanity_free
- guardrails hub install hub://guardrails/competitor_check


------------------------------------  How to Obtain Google SSO Credentials  ------------------------------------

pip install django-google-sso

Open the [Google Cloud Console](https://console.cloud.google.com/welcome/new?pli=1) and log in with your Google account.

# Create a New Project
  Click on the "Select a Project" dropdown at the top of the page.
  Click "New Project" and provide a name for your project.
  Click "Create" to set up the new project.
  
# Enable the OAuth Consent Screen

  In the navigation menu, go to APIs & Services > OAuth consent screen.
  Select "External" for user type.
  Fill out the required details, such as the app name, email.
  Add your domain (if applicable) and specify authorized domains.
  Save and continue.

# Go to APIs & Services > Credentials.
  
  Click "Create Credentials" and select OAuth 2.0 Client IDs.
  Choose Web Application as the application type.
  Add Authorized Redirect URIs (e.g., https://yourdomain.com/google_sso/callback/ or http://localhost:8000/google_sso/callback/ for local testing).
  Download Your Credentials

After creating the credentials, you’ll see a Client ID and Client Secret also get the  PROJECT ID by clicking on the project.
Set Up the Credentials in Project.