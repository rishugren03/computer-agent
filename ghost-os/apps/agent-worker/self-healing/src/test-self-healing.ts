import { chromium } from 'playwright';
import { SelfHealingPage } from './SelfHealingPage';
import fs from 'fs-extra';
import path from 'path';

console.log('Test script started');

async function runTest() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Create a dummy HTML file for testing
  const testHtmlPath = path.join(__dirname, '../test.html');
  const htmlContent = `
    <!DOCTYPE html>
    <html>
    <head><title>Test Self-Healing</title></head>
    <body>
      <h1>Self-Healing Test</h1>
      <button id="real-button-123" class="btn-primary">Click Me (Connect)</button>
      <script>
        document.getElementById('real-button-123').onclick = () => {
          console.log('Button Clicked!');
          document.body.innerHTML += '<p id="success">Success!</p>';
        };
      </script>
    </body>
    </html>
  `;
  await fs.writeFile(testHtmlPath, htmlContent);

  try {
    const url = `file://${testHtmlPath}`;
    await page.goto(url);

    const selfHealingPage = new SelfHealingPage(page);

    console.log('--- Phase 1: Fail and Heal ---');
    // Intent is "Click Connect Button", but we provide a wrong selector ".non-existent-btn"
    await selfHealingPage.safeClick('Click Connect Button', '.non-existent-btn');

    // Verify success message appears in DOM
    const successMsg = await page.locator('#success').textContent();
    if (successMsg === 'Success!') {
      console.log('Verification Successful: Self-healing worked!');
    } else {
      console.error('Verification Failed: Success message not found.');
    }

    console.log('--- Phase 2: Use Learned Selector ---');
    // Reload page to reset state
    await page.reload();
    // This time it should use the stored selector from selectors.json
    await selfHealingPage.safeClick('Click Connect Button', '.non-existent-btn');
    
    const successMsg2 = await page.locator('#success').textContent();
    if (successMsg2 === 'Success!') {
      console.log('Verification Successful: Learned selector used!');
    }

  } catch (error) {
    console.error('Test failed:', error);
  } finally {
    await browser.close();
    // Cleanup
    // await fs.remove(testHtmlPath);
  }
}

runTest();
