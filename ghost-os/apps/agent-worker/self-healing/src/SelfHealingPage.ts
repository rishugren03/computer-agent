import { Page, Locator } from 'playwright';
import { LLMClient } from './LLMClient';
import { SelectorStore } from './SelectorStore';
import path from 'path';
import fs from 'fs-extra';

export class SelfHealingPage {
  private page: Page;
  private llm: LLMClient;
  private store: SelectorStore;

  constructor(page: Page) {
    this.page = page;
    this.llm = new LLMClient();
    this.store = new SelectorStore(path.join(__dirname, '../data'));
  }

  public async safeClick(intent: string, defaultSelector: string): Promise<void> {
    const selector = this.store.getSelector(intent, defaultSelector);
    
    try {
      console.log(`[Self-Healing] Attempting to click: ${intent} using selector: ${selector}`);
      await this.page.click(selector, { timeout: 5000 });
      console.log(`[Self-Healing] Successfully clicked: ${intent}`);
    } catch (error: any) {
      console.warn(`[Self-Healing] Failed to click: ${intent}. Error: ${error.message}`);
      
      const healingResult = await this.heal(intent, defaultSelector, error.message);
      
      if (healingResult.status === 'fixed' && healingResult.newSelector) {
        console.log(`[Self-Healing] Retry clicking: ${intent} with new selector: ${healingResult.newSelector}`);
        await this.page.click(healingResult.newSelector);
        
        console.log(`[Self-Healing] Success! Updating selector store for: ${intent}`);
        await this.store.saveSelector(intent, healingResult.newSelector);
      } else {
        throw new Error(`Self-healing failed for intent: "${intent}". Original error: ${error.message}`);
      }
    }
  }

  private async heal(intent: string, originalSelector: string, errorMessage: string) {
    console.log(`[Self-Healing] Starting healing process for: ${intent}`);
    
    // Gather context
    const screenshotPath = path.join(__dirname, `../screenshots/failure-${Date.now()}.png`);
    await fs.ensureDir(path.dirname(screenshotPath));
    await this.page.screenshot({ path: screenshotPath });
    
    // Extract HTML context (simplified for now: full body or relevant area)
    // In a real scenario, we might want to prune the DOM or target the area around the original selector
    const htmlContext = await this.page.evaluate(() => document.body.innerHTML);
    
    // Call LLM
    return await this.llm.healSelector(intent, htmlContext, errorMessage);
  }
}
