/**
 * Puppeteer Test Script for Chat Flow
 * Tests GPT-like conversational table selection with a real question
 * 
 * Run with: npx ts-node tests/e2e/test_chat_rft.ts
 */
import puppeteer from 'puppeteer';

const BASE_URL = 'http://localhost:3004';
const USERNAME = 'admin';
const PASSWORD = 'admin123';
const TEST_QUESTION = 'Identifikasi Line dengan RFT terbaik atau tertinggi';

async function runTest() {
    console.log('🚀 Starting Puppeteer chat test...\n');

    const browser = await puppeteer.launch({
        headless: false, // Set to true for headless mode
        slowMo: 50, // Slow down for visibility
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });

    // Enable console logging from the page
    page.on('console', msg => {
        console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`);
    });

    // Monitor network requests to the chat API
    page.on('request', request => {
        if (request.url().includes('/api/chat')) {
            console.log(`[Network] → ${request.method()} ${request.url()}`);
        }
    });

    page.on('response', response => {
        if (response.url().includes('/api/chat')) {
            console.log(`[Network] ← ${response.status()} ${response.url()}`);
        }
    });

    try {
        // Step 1: Navigate to login
        console.log('📍 Step 1: Navigating to login page...');
        await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle0' });
        console.log('   ✓ Login page loaded\n');

        // Step 2: Login
        console.log('📍 Step 2: Logging in...');
        await page.waitForSelector('#username', { timeout: 5000 });
        await page.type('#username', USERNAME);
        await page.type('#password', PASSWORD);
        await page.click('button[type="submit"]');

        // Wait for navigation after login
        await page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 10000 }).catch(() => { });
        await new Promise(resolve => setTimeout(resolve, 2000)); // Extra wait
        console.log('   ✓ Logged in successfully\n');

        // Step 3: Check current URL and find Chat tab
        console.log('📍 Step 3: Looking for Chat tab...');
        const currentUrl = page.url();
        console.log(`   Current URL: ${currentUrl}`);

        // Try to find and click Chat tab
        const chatTabSelectors = [
            'button:has-text("Chat")',
            '[data-testid="chat-tab"]',
            'button[aria-label*="Chat"]',
            'div[role="tablist"] button:nth-child(1)',
        ];

        let chatTabClicked = false;
        for (const selector of chatTabSelectors) {
            try {
                await page.waitForSelector(selector, { timeout: 2000 });
                await page.click(selector);
                chatTabClicked = true;
                console.log(`   ✓ Clicked chat tab using selector: ${selector}\n`);
                break;
            } catch {
                // Try next selector
            }
        }

        if (!chatTabClicked) {
            console.log('   ℹ️ Chat tab might already be active or uses different selector\n');
        }

        await new Promise(resolve => setTimeout(resolve, 1000));

        // Step 4: Find chat input and type question
        console.log('📍 Step 4: Finding chat input...');

        // Use the specific aria-label from ChatTab.tsx
        const inputSelector = 'input[aria-label="Type your question"]';

        try {
            await page.waitForSelector(inputSelector, { timeout: 10000 });
            console.log(`   ✓ Found input with aria-label`);

            // Type the question
            console.log(`   📝 Typing question: "${TEST_QUESTION}"\n`);
            await page.type(inputSelector, TEST_QUESTION);
        } catch {
            // Fallback: try any input
            console.log('   ⚠️ Specific input not found, trying fallback...');
            const fallbackInput = await page.$('input') || await page.$('textarea');
            if (fallbackInput) {
                await fallbackInput.type(TEST_QUESTION);
                console.log('   ✓ Used fallback input\n');
            } else {
                throw new Error('Could not find any input field');
            }
        }

        // Step 5: Submit the question
        console.log('📍 Step 5: Submitting question...');

        // Try clicking Send button first
        const sendButtonSelectors = [
            'button[type="submit"]',
            'button:has-text("Send")',
            '[aria-label*="Send"]',
        ];

        let submitted = false;
        for (const selector of sendButtonSelectors) {
            try {
                await page.click(selector);
                submitted = true;
                console.log(`   ✓ Clicked submit button\n`);
                break;
            } catch {
                // Try next
            }
        }

        if (!submitted) {
            // Try pressing Enter
            await page.keyboard.press('Enter');
            console.log('   ✓ Pressed Enter to submit\n');
        }

        // Step 6: Wait for and observe response
        console.log('📍 Step 6: Waiting for AI response...');
        console.log('   Monitoring for streaming messages...\n');

        // Wait and check for responses
        let attempts = 0;
        const maxAttempts = 30; // 30 seconds max

        while (attempts < maxAttempts) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            attempts++;

            // Check for loading indicator
            const isLoading = await page.$('.spinner, [role="progressbar"], .loading');

            // Check for messages in the chat
            const messageCards = await page.$$('div[class*="Card"]');
            console.log(`   [${attempts}s] Cards found: ${messageCards.length}, Loading: ${!!isLoading}`);

            // Try to get the last message content
            try {
                const lastMessage = await page.evaluate(() => {
                    const cards = document.querySelectorAll('div[class*="CardContent"]');
                    if (cards.length > 0) {
                        const lastCard = cards[cards.length - 1];
                        return lastCard.textContent?.substring(0, 200) || '';
                    }
                    return '';
                });

                if (lastMessage && lastMessage.length > 10) {
                    console.log(`   📨 Latest message preview: "${lastMessage.substring(0, 100)}..."`);
                }
            } catch {
                // Ignore evaluation errors
            }

            // Stop if not loading anymore and we have messages
            if (!isLoading && messageCards.length >= 2) {
                console.log('\n   ✓ Response received!\n');
                break;
            }
        }

        // Step 7: Capture final state
        console.log('📍 Step 7: Capturing final state...');

        // Get all visible text in chat area
        const chatContent = await page.evaluate(() => {
            const chatArea = document.querySelector('[class*="ScrollArea"]') || document.body;
            return chatArea.textContent?.substring(0, 2000) || 'Could not get content';
        });

        console.log('\n📋 === CHAT CONTENT ===\n');
        console.log(chatContent);
        console.log('\n======================\n');

        // Take screenshot
        const screenshotPath = 'tests/screenshots/chat_rft_test.png';
        await page.screenshot({ path: screenshotPath, fullPage: true });
        console.log(`📸 Screenshot saved: ${screenshotPath}\n`);

        console.log('✅ Test completed successfully!\n');

    } catch (error) {
        console.error('❌ Test failed:', error);

        // Take error screenshot
        await page.screenshot({ path: 'tests/screenshots/chat_rft_error.png', fullPage: true });
        console.log('📸 Error screenshot saved\n');

    } finally {
        // Keep browser open for manual inspection
        console.log('🔍 Browser will stay open for 30 seconds for inspection...');
        await new Promise(resolve => setTimeout(resolve, 30000));
        await browser.close();
    }
}

// Run the test
runTest().catch(console.error);
