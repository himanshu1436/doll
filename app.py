import asyncio
from fastapi import FastAPI, Request
from pydoll.browser.chrome import Chrome
from pydoll.constants import By

app = FastAPI()

@app.get("/jobs")
async def get_jobs():
    jobs = []
    
    async with Chrome() as browser:
        await browser.start()
        page = await browser.get_page()
        
        await page.go_to('https://www.amazon.jobs/content/en-gb/teams/wwas/india?country%5B%5D=IN',timeout=10000)

        hasNextPage = True

        while(hasNextPage):
            jobsContainer = await page.wait_element(By.CSS_SELECTOR, '.jobs-module_root__gY8Hp', timeout=10000)
            jobList = await jobsContainer.find_elements(By.CSS_SELECTOR, 'li')

            for job in jobList:
                jobLink = await job.find_element(By.CSS_SELECTOR, 'a')
                jobTitleText = await jobLink.get_element_text()
                jobUrl = 'https://amazon.jobs' + jobLink.get_attribute('href')
                
                jobs.append({"title": jobTitleText, "link": jobUrl})

            nextButton = await page.find_element(By.CSS_SELECTOR, '[aria-label="Next page"]')
            tabIndex = nextButton.get_attribute('tabindex')
            
            if(tabIndex == '-1'):
                hasNextPage = False
            else:
                await nextButton.click()
                await asyncio.sleep(4)
                await page.wait_element(By.CSS_SELECTOR, '.jobs-module_root__gY8Hp', timeout=10000)
    
    return {"joinbs": jobs}


@app.post("/jobDetails")
async def get_job_details(req : Request):
    data = await req.json()
    job_url = data['url']

    async with Chrome() as browser:
        
        await browser.start()

        page = await browser.get_page()
        await page.go_to(job_url, timeout=10000)

        jobDetailElement = await page.find_element(By.CSS_SELECTOR, '#job-detail')
        
        jobTitleElement = await jobDetailElement.find_element(By.CSS_SELECTOR, '.title')
        jobTitle = await jobTitleElement.get_element_text()

        sideBarElement = await jobDetailElement.find_element(By.CSS_SELECTOR, '.sidebar')
        
        jobLocationElement = await sideBarElement.find_element(By.CSS_SELECTOR, 'ul li')
        jobLocation = await jobLocationElement.get_element_text()

        jobInformationElements = await jobDetailElement.find_elements(By.CSS_SELECTOR, '.content .section')
        length = len(jobInformationElements)
        
        if length > 0:
            jobInformationElements.pop(0)

        jobDescriptionParagraphElement = await jobInformationElements[0].find_element(By.CSS_SELECTOR, 'p')
        jobDescriptionParagraptHTML = await jobDescriptionParagraphElement.inner_html

        print(jobDescriptionParagraptHTML)


        
        return {"title": jobTitle, "location": jobLocation}
        

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)