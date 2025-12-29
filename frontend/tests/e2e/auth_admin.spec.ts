import puppeteer, { Browser, Page } from 'puppeteer';

const BASE_URL = 'http://localhost:3004';
const BACKEND_URL = 'http://localhost:1234'; // For cleanup if needed

describe('Auth & Admin E2E Flow', () => {
    let browser: Browser;
    let page: Page;

    beforeAll(async () => {
        browser = await puppeteer.launch({
            headless: true, // Run visually for debugging if set to false
            args: ['--no-sandbox', '--disable-setuid-sandbox'],
            defaultViewport: { width: 1280, height: 800 }
        });
        page = await browser.newPage();
    });

    afterAll(async () => {
        if (browser) await browser.close();
    });

    const generateUser = () => {
        const r = Math.random().toString(36).substring(7);
        return {
            username: `e2e_user_${r}`,
            password: 'TestPassword123!',
            email: `e2e_${r}@example.com`
        };
    };

    const testUser = generateUser();
    const adminUser = { username: 'admin', password: 'admin123' };

    it('1. Should allow user signup', async () => {
        await page.goto(`${BASE_URL}/login`);
        await page.waitForSelector('a[href="/signup"]');
        await page.click('a[href="/signup"]');

        // Fill signup form
        await page.waitForSelector('#username');
        await page.type('#username', testUser.username);
        await page.type('#password', testUser.password);
        await page.type('#confirmPassword', testUser.password);
        await page.type('#email', testUser.email);

        // Submit
        const [response] = await Promise.all([
            // page.waitForNavigation(), // Signup might redirect or show toast
            page.click('button[type="submit"]')
        ]);

        // Verify success message (toast or text)
        // Adjust selector based on actual success UI
        // Assuming toast or text appearing
        await page.waitForFunction(
            (text: string) => document.body.innerText.includes(text),
            {},
            'Signup request submitted'
        );
    }, 60000);

    it('2. Should log in as admin and approve user', async () => {
        await page.goto(`${BASE_URL}/login`);

        // Login as Admin
        await page.type('#username', adminUser.username);
        await page.type('#password', adminUser.password);

        await Promise.all([
            page.waitForNavigation(),
            page.click('button[type="submit"]')
        ]);

        // Go to Admin Panel
        // Assuming Admin Panel is in sidebar or accessible
        // Sidebar usually has role check.
        // Try navigating directly if possible, or click sidebar

        // Wait for sidebar to load
        await page.waitForSelector('nav');

        // Look for Admin Panel link (Shield icon)
        // Finding element by text might be safer
        await page.evaluate(() => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const adminBtn = buttons.find(b => b.textContent?.includes('Admin Panel'));
            if (adminBtn) adminBtn.click();
        });

        // Wait for Admin Panel tabs
        await page.waitForSelector('button[role="tab"]');

        // Click Pending Registrations tab (contains 'Pending')
        const tabs = await page.$$('button[role="tab"]');
        for (const tab of tabs) {
            const text = await (await tab.getProperty('textContent')).jsonValue();
            if (text && (text as string).includes('Pending')) {
                await tab.click();
                break;
            }
        }

        // Find row with our username
        await page.waitForFunction(
            (username: string) => document.body.innerText.includes(username),
            {},
            testUser.username
        );

        // Click Approve button for this user
        // Using evaluate to find and click
        await page.evaluate((username: string) => {
            const rows = Array.from(document.querySelectorAll('tr')); // Table rows
            const targetRow = rows.find(r => r.innerText.includes(username));
            if (targetRow) {
                const approveBtn = Array.from(targetRow.querySelectorAll('button'))
                    .find(b => b.textContent?.includes('Approve'));
                if (approveBtn) (approveBtn as HTMLElement).click();
            }
        }, testUser.username);

        // Wait for approval msg
        await new Promise(r => setTimeout(r, 1000)); // Wait for API

    }, 90000);

    it('3. Should verify approved user can login', async () => {
        // Logout first
        // Find logout button (usually in sidebar footer or profile menu)
        // Let's just go to login page, it usually clears session or redirect if logged in

        // Force clear cookies/storage to simulate logout if needed
        await page.deleteCookie(...await page.cookies());
        await page.evaluate(() => localStorage.clear());

        await page.goto(`${BASE_URL}/login`);

        await page.type('#username', testUser.username);
        await page.type('#password', testUser.password);

        await Promise.all([
            page.waitForNavigation(),
            page.click('button[type="submit"]')
        ]);

        // Verify dashboard access
        await page.waitForSelector('nav'); // Sidebar should exist
        const content = await page.content();
        expect(content).toContain(testUser.username); // User display name usually shown

    }, 45000);

    it('4. Should check OneDrive upload UI presence', async () => {
        // Navigate to Upload tab
        // Click 'Upload' in sidebar
        await page.evaluate(() => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const uploadBtn = buttons.find(b => b.textContent?.includes('Upload'));
            if (uploadBtn) uploadBtn.click();
        });

        // Wait for OneDrive card
        await page.waitForSelector('h3'); // Card headers
        const hasOneDrive = await page.evaluate(() => {
            return document.body.innerText.includes('Upload to OneDrive');
        });
        expect(hasOneDrive).toBe(true);

        // Click load subfolders (if button exists)
        // Or just check if dropdown exists
    });
});
