import inspect
from typing import Annotated

from agentq.core.agent.captcha_agent import CaptchaAgent
from agentq.core.models.models import CaptchaAgentInput, CaptchaAgentOutput
from agentq.core.skills.enter_text_and_click import enter_text_and_click
from agentq.core.skills.get_screenshot import get_screenshot
from agentq.core.web_driver.playwright import PlaywrightManager
from agentq.utils.logger import logger


async def solve_captcha(
    text_selector: Annotated[
        str,
        "The properly formatted DOM selector query, for example [mmid='1234'], where the captcha text will be entered. Use mmid attribute. mmid will always be a number",
    ],
    click_selector: Annotated[
        str,
        "The properly formatted DOM selector query, for example [mmid='1234'], for the element that will be clicked after captch text entry. mmmid will be alwayes be a number",
    ],
    wait_before_click_execution: Annotated[
        float, "Optional wait time in seconds before executing the click."
    ],
) -> Annotated[
    str, "A message indicating success of failure of the captcha solving and submitting"
]:
    """
    Solves a captcha, enters into the text element and submits it by clicking another element.

    Parameters:
    - text_selector: The selector for the element to enter the captcha into. It should be a properly formatted DOM selector query, for example [mmid='1234'], where the captcha text will be entered. Use the mmid attribute.
    - click_selector: The selector for the element to click post captcha is entered. It should be a properly formatted DOM selector query, for example [mmid='1234'].
    - wait_before_click_execution: Optional wait time in seconds before executing the click action. Default is 0.0.

    Returns:
    - A message indicating the success or failure of the cathcha entry and click.

    Raises:
    - ValueError: If no active page is found. The OpenURL command opens a new page.

    Example usage:
    ```
    await solve_captcha("[mmid='1234']", "[mmid='5678']", wait_before_click_execution=1.5)
    ```
    -
    """
    logger.info("Solving captcha")

    browser_manager = PlaywrightManager(browser_type="chromium", headless=False)

    page = await browser_manager.get_current_page()

    if page is None:
        logger.error("No active page found")
        raise ValueError("No active page found. OpenURL command opens a new page")

    # Take ss for logging
    function_name = inspect.currentframe().f_code.co_name
    await browser_manager.highlight_element(text_selector, True)
    await browser_manager.take_screenshots(f"{function_name}_start", page=page)

    screenshot = await get_screenshot()
    captcha_agent = CaptchaAgent()
    input: CaptchaAgentInput = CaptchaAgentInput(objective="Solve this captcha")

    try:
        captcha_output: CaptchaAgentOutput = await captcha_agent.run(input, screenshot)
    except Exception as e:
        await browser_manager.take_screenshots(f"{function_name}_end", page=page)
        logger.error(f"Error in captcha_agent.run: {str(e)}")
        return "Failed to solve the captcha. Error in running the Captcha Agent"

    if not captcha_output.success:
        await browser_manager.take_screenshots(f"{function_name}_end", page=page)
        return "Failed to solve the captcha. Captcha agent did not succeed."

    success_msg = (
        f"Success. Successfully solved the captcha {captcha_output.captcha}.\n"
    )
    result = {
        "summary_message": success_msg,
        "detailed_message": f"{success_msg}",
    }

    # enter text and click
    enter_text_and_click_result = await enter_text_and_click(
        text_selector=text_selector,
        text_to_enter=captcha_output.captcha,
        click_selector=click_selector,
        wait_before_click_execution=wait_before_click_execution,
    )

    if not enter_text_and_click_result.startswith("Success"):
        await browser_manager.take_screenshots(f"{function_name}_end", page)
        return f"Solved the captcha but failed to enter it & click '{enter_text_and_click_result}' into element with text selector '{text_selector} & click selector {click_selector}'. Check that the selctor is valid."

    result["detailed_message"] += f"{enter_text_and_click_result}"

    return result["detailed_message"]
