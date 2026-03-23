import fs from 'fs-extra';
import path from 'path';

export class SelectorStore {
  private filePath: string;
  private selectors: Record<string, string> = {};

  constructor(baseDir: string) {
    this.filePath = path.join(baseDir, 'selectors.json');
    this.load();
  }

  private load() {
    if (fs.existsSync(this.filePath)) {
      try {
        this.selectors = fs.readJsonSync(this.filePath);
      } catch (error) {
        console.error('Failed to load selectors.json:', error);
        this.selectors = {};
      }
    }
  }

  public getSelector(intent: string, defaultSelector: string): string {
    return this.selectors[intent] || defaultSelector;
  }

  public async saveSelector(intent: string, newSelector: string): Promise<void> {
    this.selectors[intent] = newSelector;
    try {
      await fs.writeJson(this.filePath, this.selectors, { spaces: 2 });
    } catch (error) {
      console.error('Failed to save selectors.json:', error);
    }
  }
}
