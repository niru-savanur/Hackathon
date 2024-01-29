from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
# import pdfkit

# Set the path to the ChromeDriver executable
chrome_driver_path = 'C:/Users/savan/Downloads/chromedriver_win32/chromedriver.exe'

# Set the URL of the webpage you want to parse
url = 'https://www.netmeds.com/offers/12-month-netmeds-first-membership-worth-rs-499'


service = Service(ChromeDriverManager().install())
options = webdriver.ChromeOptions()


# Create a webdriver instance (you can use other browsers as well)
driver = webdriver.Chrome()

# Open the webpage
driver.get(url)

# Wait for the page to load (you might need to adjust the wait time)
driver.implicitly_wait(10)

# Get the page source
page_source = driver.page_source

# Close the browser
driver.quit()

# Parse the HTML content using Beautiful Soup
soup = BeautifulSoup(page_source, 'html.parser')

# Get the text content of the webpage
webpage_text = soup.get_text()

# print(webpage_text)
# Save the contents to a PDF file
# pdfkit.from_string(webpage_text, 'output.pdf')
import re
pattern = re.compile(r'https://(.*?\.com)')
# pattern = re.compile(r'https://(.*?\.in)')

# Find the match in the URL string
match = pattern.search(url)

with open(str(match.group(1)) + '.txt', 'w', encoding="utf-8") as file:
    file.write(webpage_text)