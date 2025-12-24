/**
 * Puppeteer Test Setup
 * Configures browser instance for E2E tests.
 */
import puppeteer, { Browser, Page } from 'puppeteer';

// Global browser instance
let browser: Browser;
let page: Page;

// Test configuration
export const TEST_CONFIG = {
    baseUrl: 'http://localhost:3004',
    timeout: 10000,
    headless: true,
    slowMo: 0, // Set to 100 for debugging
};

/**
 * Setup browser before all tests.
 */
beforeAll(async () => {
    browser = await puppeteer.launch({
        headless: TEST_CONFIG.headless,
        slowMo: TEST_CONFIG.slowMo,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
});

/**
 * Create new page before each test.
 */
beforeEach(async () => {
    page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 720 });
});

/**
 * Close page after each test.
 */
afterEach(async () => {
    if (page) {
        await page.close();
    }
});

/**
 * Close browser after all tests.
 */
afterAll(async () => {
    if (browser) {
        await browser.close();
    }
});

/**
 * Get the current page instance.
 */
export function getPage(): Page {
    return page;
}

/**
 * Get the browser instance.
 */
export function getBrowser(): Browser {
    return browser;
}

/**
 * Navigate to a path on the test server.
 */
export async function navigateTo(path: string): Promise<void> {
    await page.goto(`${TEST_CONFIG.baseUrl}${path}`, {
        waitUntil: 'networkidle0',
    });
}

/**
 * Wait for selector and click.
 */
export async function clickElement(selector: string): Promise<void> {
    await page.waitForSelector(selector, { timeout: TEST_CONFIG.timeout });
    await page.click(selector);
}

/**
 * Type into an input field.
 */
export async function typeInto(selector: string, text: string): Promise<void> {
    await page.waitForSelector(selector, { timeout: TEST_CONFIG.timeout });
    await page.type(selector, text);
}

/**
 * Get text content of an element.
 */
export async function getTextContent(selector: string): Promise<string> {
    await page.waitForSelector(selector, { timeout: TEST_CONFIG.timeout });
    return page.$eval(selector, (el) => el.textContent || '');
}

/**
 * Check if element exists.
 */
export async function elementExists(selector: string): Promise<boolean> {
    try {
        await page.waitForSelector(selector, { timeout: 2000 });
        return true;
    } catch {
        return false;
    }
}

/**
 * Take screenshot for debugging.
 */
export async function takeScreenshot(name: string): Promise<void> {
    await page.screenshot({
        path: `tests/screenshots/${name}.png`,
        fullPage: true,
    });
}

/**
 * Login helper for authenticated tests.
 */
export async function login(username: string, password: string): Promise<void> {
    await navigateTo('/login');
    await typeInto('#username', username);
    await typeInto('#password', password);
    await clickElement('button[type="submit"]');
    // Wait for auth to complete
    await new Promise(resolve => setTimeout(resolve, 3000));
}
