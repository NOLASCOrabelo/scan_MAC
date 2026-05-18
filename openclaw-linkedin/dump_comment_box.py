import os, time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import sys

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()
li_at = os.getenv('LINKEDIN_LI_AT')

JS_CLICK_COMMENT = '''
() => {
    function queryAllShadow(root, selector) {
        const found = [];
        try { found.push(...root.querySelectorAll(selector)); } catch(e) {}
        for (const el of root.querySelectorAll('*')) {
            if (el.shadowRoot) found.push(...queryAllShadow(el.shadowRoot, selector));
        }
        return found;
    }
    const btns = queryAllShadow(document, 'button');
    for (const b of btns) {
        const label = ((b.getAttribute('aria-label') || '') + ' ' + (b.innerText || '')).toLowerCase();
        if (label.includes('comment') || label.includes('comentar') || label.includes('comentário')) {
            b.click();
            return true;
        }
    }
    return false;
}
'''

JS_DUMP_BOX = '''
() => {
    function queryAllShadow(root, selector) {
        const found = [];
        try { found.push(...root.querySelectorAll(selector)); } catch(e) {}
        for (const el of root.querySelectorAll('*')) {
            if (el.shadowRoot) found.push(...queryAllShadow(el.shadowRoot, selector));
        }
        return found;
    }
    const boxes = queryAllShadow(document, '[contenteditable="true"][role="textbox"]');
    if (boxes.length > 0) {
        let container = boxes[boxes.length - 1];
        for(let i=0; i<6; i++) {
            if(container.parentElement) container = container.parentElement;
            else if(container.getRootNode && container.getRootNode().host) container = container.getRootNode().host;
            else break;
            
            if(container.tagName === 'FORM' || container.outerHTML.includes('submit')) {
                return container.outerHTML;
            }
        }
        return container.outerHTML;
    }
    return 'Box not found';
}
'''

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    context.add_cookies([{'name': 'li_at', 'value': li_at, 'domain': '.www.linkedin.com', 'path': '/'}])
    page = context.new_page()
    page.goto('https://www.linkedin.com/feed/')
    page.wait_for_load_state('domcontentloaded')
    time.sleep(10)
    
    clicked = page.evaluate(JS_CLICK_COMMENT)
    print(f"Clicked comment: {clicked}")
    time.sleep(3)
    
    # Type something to make the post button active
    page.evaluate('''() => {
        function queryAllShadow(root, selector) {
            const found = [];
            try { found.push(...root.querySelectorAll(selector)); } catch(e) {}
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot) found.push(...queryAllShadow(el.shadowRoot, selector));
            }
            return found;
        }
        const boxes = queryAllShadow(document, '[contenteditable="true"][role="textbox"]');
        if (boxes.length > 0) {
            boxes[boxes.length - 1].focus();
        }
    }''')
    page.keyboard.type("Testing comment", delay=50)
    time.sleep(2)
    
    html = page.evaluate(JS_DUMP_BOX)
    with open('comment_box_dump.html', 'w', encoding='utf-8') as f:
        f.write(html)
        
    print("Dump saved.")
    browser.close()
