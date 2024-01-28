import puppeteer from "puppeteer";

export async function getComputedTextStyles(htmlContent) {
  const browser = await puppeteer.launch({ headless: "new" });
  const page = await browser.newPage();
  await page.setContent(htmlContent);

  const result = await page.evaluate(() => {
    const allElements = Array.from(document.body.getElementsByTagName("*"));

    const leafTextElements = allElements.filter((element) => {
      // Check if the element has text content
      const hasText =
        element.textContent && element.textContent.trim().length > 0;
      // Check if the element is a leaf (has no child elements with text)
      const isLeaf = !Array.from(element.children).some(
        (child) => child.textContent.trim().length > 0
      );
      return hasText && isLeaf;
    });

    return leafTextElements.map((element) => {
      const color = window.getComputedStyle(element).color;
      const backgroundColor = window.getComputedStyle(element).backgroundColor;
      return {
        element: element.tagName,
        color,
        backgroundColor,
        text: element.textContent.trim(),
      };
    });
  });

  await browser.close();
  return result;
}
