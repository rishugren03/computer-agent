import { GoogleGenerativeAI } from "@google/generative-ai";
import * as dotenv from 'dotenv';
import path from 'path';

dotenv.config({ path: path.join(__dirname, '../../.env') });

async function listModels() {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    console.error("GEMINI_API_KEY not found");
    return;
  }
  const genAI = new GoogleGenerativeAI(apiKey);
  try {
    // There is no direct listModels in the client, but we can try a simple generation to test connectivity
    const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });
    const result = await model.generateContent("test");
    console.log("Success with gemini-1.5-flash:", result.response.text());
  } catch (error: any) {
    console.error("Failed with gemini-1.5-flash:", error.message);
    try {
        const model = genAI.getGenerativeModel({ model: "gemini-pro" });
        const result = await model.generateContent("test");
        console.log("Success with gemini-pro:", result.response.text());
    } catch (error2: any) {
        console.error("Failed with gemini-pro:", error2.message);
    }
  }
}

listModels();
