import { LLMClient } from './LLMClient';
import fs from 'fs-extra';

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error('Usage: ts-node src/cli.ts <intent> <htmlPath> [errorMessage]');
    process.exit(1);
  }

  const intent = args[0];
  const htmlPath = args[1];
  const errorMessage = args[2] || 'Timeout Error';

  try {
    if (!fs.existsSync(htmlPath)) {
      throw new Error(`HTML file not found: ${htmlPath}`);
    }

    const htmlContext = await fs.readFile(htmlPath, 'utf-8');
    const llm = new LLMClient();
    
    const result = await llm.healSelector(intent, htmlContext, errorMessage);
    console.log(JSON.stringify(result));
  } catch (error: any) {
    console.error('CLI Error:', error.message);
    console.log(JSON.stringify({ status: 'failed', newSelector: '' }));
    process.exit(1);
  }
}

main();
