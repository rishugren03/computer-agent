import { GoogleGenerativeAI } from "@google/generative-ai";
import * as dotenv from 'dotenv';
import path from 'path';

// Load .env from root
dotenv.config({ path: path.join(__dirname, '../../.env') });

export class LLMClient {
  private genAI: GoogleGenerativeAI;
  private model: any;

  constructor() {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      throw new Error("GEMINI_API_KEY not found in environment");
    }
    this.genAI = new GoogleGenerativeAI(apiKey);
    this.model = this.genAI.getGenerativeModel({ model: "gemini-2.0-flash" });
  }

  public async healSelector(
    intent: string,
    htmlContext: string,
    errorMessage: string
  ): Promise<{ status: string; newSelector: string }> {
    const prompt = `
      You are an expert QA Automation Engineer specialized in Playwright.
      A browser automation script failed to perform an action.
      
      INTENT: "${intent}"
      ERROR: "${errorMessage}"
      
      PAGE CONTEXT (HTML):
      \`\`\`html
      ${htmlContext}
      \`\`\`
      
      Based on the intent and the HTML provided, identify the best Playwright-compatible CSS or XPath selector for the element the user intended to interact with.
      
      Respond only with a structured JSON object in the following format:
      {
        "status": "fixed",
        "newSelector": ".your-selector-here"
      }
      
      If you cannot find a suitable selector, respond with:
      {
        "status": "failed",
        "newSelector": ""
      }
    `;

    try {
      const result = await this.model.generateContent(prompt);
      const response = await result.response;
      const text = response.text();
      
      // Extract JSON from response (Gemini sometimes wraps in markdown blocks)
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
      
      throw new Error("Failed to parse JSON from LLM response");
    } catch (error) {
      console.error('LLM Healing failed:', error);
      return { status: "failed", newSelector: "" };
    }
  }
}
