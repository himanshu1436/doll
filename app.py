import asyncio
from fastapi import FastAPI, Request, HTTPException
from pydoll.browser.chrome import Chrome
from pydoll.constants import By
import logging

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()


async def initialize_browser():
    """Initialize and return a Chrome browser instance."""
    browser = Chrome()
    await browser.start()
    return browser, await browser.get_page()

async def navigate_to_url(page, url, timeout=10000):
    """Navigate to a URL and handle potential errors."""
    try:
        await page.go_to(url, timeout=timeout)
        return True
    except Exception as e:
        logger.error(f"Failed to navigate to URL {url}: {str(e)}")
        return False

async def wait_for_element_with_retry(page, selector, timeout=10000, max_retries=2):
    retries = 0
    while retries <= max_retries:
        try:
            element = await page.wait_element(By.CSS_SELECTOR, selector, timeout=timeout)
            return element
        except Exception as e:
            if retries < max_retries:
                logger.warning(f"Element {selector} not found, refreshing page. Retry {retries+1}/{max_retries}")
                await page.refresh()
                await asyncio.sleep(3)
                retries += 1
            else:
                logger.error(f"Element {selector} not found after {max_retries} retries: {str(e)}")
                return None
    return None

async def get_job_listings(page, container_selector, item_selector):
    """Extract job listings from the page."""
    container = await wait_for_element_with_retry(page, container_selector)
    if not container:
        return []
    
    try:
        return await container.find_elements(By.CSS_SELECTOR, item_selector)
    except Exception as e:
        logger.error(f"Failed to find job listings: {str(e)}")
        return []

async def extract_job_info(job_element):
    """Extract title and URL from a job listing element."""
    try:
        link_element = await job_element.find_element(By.CSS_SELECTOR, 'a')
        title = await link_element.get_element_text()
        url = 'https://amazon.jobs' + link_element.get_attribute('href')
        return {"title": title, "link": url}
    except Exception as e:
        logger.warning(f"Failed to extract job info: {str(e)}")
        return None

async def check_next_page(page, next_button_selector):
    """Check if there's a next page and navigate to it if available."""
    try:
        next_button = await page.find_element(By.CSS_SELECTOR, next_button_selector)
        tab_index = next_button.get_attribute('tabindex')
        
        if tab_index == '-1':
            return False
        
        await next_button.click()
        await asyncio.sleep(4) 
        return True
    except Exception as e:
        logger.warning(f"Failed to navigate to next page: {str(e)}")
        return False

async def get_job_title(job_detail_element):
    """Extract job title from job detail element."""
    try:
        title_element = await job_detail_element.find_element(By.CSS_SELECTOR, '.title')
        return await title_element.get_element_text()
    except Exception as e:
        logger.warning(f"Failed to get job title: {str(e)}")
        return "Not available"

async def get_job_location(job_detail_element):
    """Extract job location from job detail element."""
    try:
        sidebar = await job_detail_element.find_element(By.CSS_SELECTOR, '.sidebar')
        location_element = await sidebar.find_element(By.CSS_SELECTOR, 'ul li')
        return await location_element.get_element_text()
    except Exception as e:
        logger.warning(f"Failed to get job location: {str(e)}")
        return "Not available"

def clean_html_content(html_content):
    """Remove <p> tags from the beginning and end of HTML content."""
    if html_content.startswith('<p>'):
        html_content = html_content[3:]
    if html_content.endswith('</p>'):
        html_content = html_content[:-4]
    return html_content

def process_html_to_paragraphs(html_content):
    """Process HTML content to extract paragraphs and lines."""
    processed_html = html_content.replace('<br><br>', '||PARAGRAPH_BREAK||')
    processed_html = processed_html.replace('<br>', '||LINE_BREAK||')
    return processed_html.split('||PARAGRAPH_BREAK||')

def extract_text_from_paragraphs(paragraphs):
    """Extract clean text lines from paragraphs."""
    result = []
    for paragraph in paragraphs:
        lines = paragraph.split('||LINE_BREAK||')
        for line in lines:
            clean_line = line.strip()
            if clean_line:
                result.append(clean_line)
    return result

async def extract_section_content(section_element):
    """Extract and process content from a section element."""
    try:
        paragraph_element = await section_element.find_element(By.CSS_SELECTOR, 'p')
        html_content = await paragraph_element.inner_html
        
        cleaned_html = clean_html_content(html_content)
        paragraphs = process_html_to_paragraphs(cleaned_html)
        return extract_text_from_paragraphs(paragraphs)
    except Exception as e:
        logger.warning(f"Failed to extract section content: {str(e)}")
        return []

def separate_roles_and_description(text_lines):
    """Separate roles & responsibilities from general description."""
    description = []
    roles = []
    
    in_roles_section = False
    
    for line in text_lines:
        if "Roles and Responsibilities" in line:
            in_roles_section = True
            roles.append(line)
        elif in_roles_section:
            roles.append(line)
        else:
            description.append(line)
            
    return description, roles


@app.get("/jobs")
async def get_jobs():
    """API endpoint to get all Amazon job listings."""
    jobs = []
    
    try:
        async with Chrome() as browser:
            await browser.start()
            page = await browser.get_page()
            
            if not await navigate_to_url(page, 'https://www.amazon.jobs/content/en-gb/teams/wwas/india?country%5B%5D=IN'):
                return {"error": "Failed to navigate to Amazon jobs page"}

            has_next_page = True
            jobs_container_selector = '.jobs-module_root__gY8Hp'
            
            while has_next_page:
                job_elements = await get_job_listings(page, jobs_container_selector, 'li')
                
                if not job_elements:
                    return {"error": "Failed to find job listings container after multiple retries"}
                
                for job_element in job_elements:
                    job_info = await extract_job_info(job_element)
                    if job_info:
                        jobs.append(job_info)
                
                container = await wait_for_element_with_retry(page, jobs_container_selector)
                if not container:
                    break
                    
                has_next_page = await check_next_page(page, '[aria-label="Next page"]')
        
        if not jobs:
            logger.warning("No jobs were found")
            return {"warning": "No jobs were found", "jobs": []}
            
        return {"jobs": jobs}
    
    except Exception as e:
        logger.error(f"Unexpected error in get_jobs: {str(e)}")
        return {"error": "Failed to retrieve jobs", "details": str(e)}


@app.post("/jobDetails")
async def get_job_details(req: Request):
    """API endpoint to get detailed information about a specific job."""
    try:
        
        try:
            data = await req.json()
            job_url = data.get('url')
            
            if not job_url:
                raise HTTPException(status_code=400, detail="URL parameter is required")
        except Exception as e:
            logger.error(f"Failed to parse request data: {str(e)}")
            return {"error": "Invalid request data", "details": str(e)}
        
        result = {
            "title": "Not available",
            "location": "Not available",
            "description": [],
            "roles_responsibilities": [],
            "qualifications": [],
            "job_url": job_url
        }
        
        async with Chrome() as browser:
            await browser.start()
            page = await browser.get_page()
            
            if not await navigate_to_url(page, job_url):
                return {"error": "Failed to navigate to job URL", **result}

            try:
                
                job_detail_element = await wait_for_element_with_retry(page, '#job-detail')
                
                if not job_detail_element:
                    return {"error": "Failed to find job details after multiple retries", **result}
                
                result["title"] = await get_job_title(job_detail_element)
                result["location"] = await get_job_location(job_detail_element)
                
                sections = await job_detail_element.find_elements(By.CSS_SELECTOR, '.content .section')
                
                if len(sections) > 0:
                    sections.pop(0) 
                    
                    if len(sections) > 0:
                        description_text = await extract_section_content(sections[0])
                        result["description"], result["roles_responsibilities"] = separate_roles_and_description(description_text)
                    
                    if len(sections) > 1:
                        result["qualifications"] = await extract_section_content(sections[1])
                
            except Exception as e:
                logger.error(f"Failed to get job details: {str(e)}")
                return {"error": "Failed to get job details", "details": str(e), **result}
        
        return result
    
    except Exception as e:
        logger.error(f"Unexpected error in get_job_details: {str(e)}")
        return {"error": "Failed to retrieve job details", "details": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)