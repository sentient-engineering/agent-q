import os
import tempfile
import time
from typing import List, Union

from playwright.async_api import BrowserContext, Page, Playwright
from playwright.async_api import async_playwright as playwright

from agentq.utils.dom_mutation_observer import (
    dom_mutation_change_detected,
    handle_navigation_for_mutation_observer,
)
from agentq.utils.logger import logger
from agentq.utils.ui_messagetype import MessageType

# TODO - Create a wrapper browser manager class that either starts a playwright manager (our solution) or a hosted browser manager like browserbase


class PlaywrightManager:
    _homepage = "https://google.com"
    _playwright = None
    _browser_context = None
    __async_initialize_done = False
    _instance = None
    _take_screenshots = False
    _screenshots_dir = None

    def __new__(cls, *args, **kwargs):  # type: ignore
        """
        Ensures that only one instance of PlaywrightManager is created (singleton pattern).
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.__initialized = False
            logger.debug("Browser instance created..")
        return cls._instance

    def __init__(
        self,
        browser_type: str = "chromium",
        headless: bool = False,
        gui_input_mode: bool = True,
        screenshots_dir: str = "",
        take_screenshots: bool = False,
    ):
        """
        Initializes the PlaywrightManager with the specified browser type and headless mode.
        Initialization occurs only once due to the singleton pattern.

        Args:
            browser_type (str, optional): The type of browser to use. Defaults to "chromium".
            headless (bool, optional): Flag to launch the browser in headless mode or not. Defaults to False (non-headless).
        """
        if self.__initialized:
            return
        self.browser_type = browser_type
        self.isheadless = headless
        self.__initialized = True
        # self.notification_manager = NotificationManager()
        # self.user_response_event = asyncio.Event()
        # if gui_input_mode:
        #     self.ui_manager: UIManager = UIManager()
        self.set_take_screenshots(take_screenshots)
        self.set_screenshots_dir(screenshots_dir)

    async def async_initialize(
        self, eval_mode: bool = False, homepage: str = "https://google.com"
    ):
        """
        Asynchronously initialize necessary components and handlers for the browser context.
        """
        if self.__async_initialize_done:
            return

        # Step 1: Ensure Playwright is started and browser context is created
        await self.start_playwright()
        self.eval_mode = eval_mode
        await self.ensure_browser_context()

        # Step 2: Deferred setup of handlers
        # await self.setup_handlers()

        self._homepage = homepage

        # Step 3: Navigate to homepage
        await self.go_to_homepage()

        self.__async_initialize_done = True

    async def ensure_browser_context(self):
        """
        Ensure that a browser context exists, creating it if necessary.
        """
        if self._browser_context is None:
            await self.create_browser_context()

    # async def setup_handlers(self):
    #     """
    #     Setup various handlers after the browser context has been ensured.
    #     """
    #     await self.set_overlay_state_handler()
    #     await self.set_user_response_handler()
    #     await self.set_navigation_handler()

    async def start_playwright(self):
        """
        Starts the Playwright instance if it hasn't been started yet. This method is idempotent.
        """
        if not PlaywrightManager._playwright:
            PlaywrightManager._playwright: Playwright = await playwright().start()

    async def stop_playwright(self):
        """
        Stops the Playwright instance and resets it to None. This method should be called to clean up resources.
        """
        # Close the browser context if it's initialized
        if PlaywrightManager._browser_context is not None:
            await PlaywrightManager._browser_context.close()
            PlaywrightManager._browser_context = None

        # Stop the Playwright instance if it's initialized
        if PlaywrightManager._playwright is not None:  # type: ignore
            await PlaywrightManager._playwright.stop()
            PlaywrightManager._playwright = None  # type: ignore

    async def create_browser_context(self):
        # load_dotenv()
        # user_data_dir: str = os.environ["BROWSER_USER_DATA_DIR"]
        # profile_directory: str = os.environ["BROWSER_PROFILE"]
        # print("Browser profile", user_data_dir)
        # logger.info("Browser Profile - " + user_data_dir + profile_directory)
        try:
            # PlaywrightManager._browser_context = (
            #     await PlaywrightManager._playwright.chromium.launch_persistent_context(
            #         user_data_dir=user_data_dir,
            #         channel="chrome",
            #         headless=self.isheadless,
            #         args=[
            #             f"--profile-directory={profile_directory}",
            #             "--disable-session-crashed-bubble",
            #             "--disable-infobars",
            #             "--no-default-browser-check",
            #             "--no-first-run",
            #             "--disable-popup-blocking",
            #             "--disable-notifications",
            #             "--disable-features=ChromeWhatsNewUI",
            #             "--disable-blink-features=AutomationControlled",
            #             "--disable-gpu",
            #             "--no-sandbox",
            #             "--disable-dev-shm-usage",
            #             "--no-first-run",
            #             "--no-zygote",
            #             "--ignore-certificate-errors",
            #             "--disable-popup-blocking",
            #             "--remote-debugging-port=9222",
            #             "--restore-last-session",
            #         ],
            #         ignore_default_args=["--enable-automation", "--bwsi"],
            #         no_viewport=True,
            #     )
            # )

            # await PlaywrightManager._playwright.chromium.launch_persistent_context(
            #     user_data_dir=user_data_dir,
            #     channel="chrome",
            #     headless=False,
            #     args=[
            #         f"--profile-directory={profile_directory}",
            #         "--remote-debugging-port=9224",
            #     ],
            #     no_viewport=True,
            # )

            # in eval mode - start a temp browser.
            if self.eval_mode:
                print("Starting in eval mode", self.eval_mode)
                new_user_dir = tempfile.mkdtemp()
                logger.info(
                    f"Starting a temporary browser instance. trying to launch with a new user dir {new_user_dir}"
                )
                PlaywrightManager._browser_context = await PlaywrightManager._playwright.chromium.launch_persistent_context(
                    new_user_dir,
                    channel="chrome",
                    headless=self.isheadless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-session-crashed-bubble",  # disable the restore session bubble
                        "--disable-infobars",  # disable informational popups,
                    ],
                    no_viewport=True,
                )
            else:
                browser = await PlaywrightManager._playwright.chromium.connect_over_cdp(
                    "http://localhost:{}".format(int(os.getenv("CHROME_PORT", "9222")))
                )
                PlaywrightManager._browser_context = browser.contexts[0]

            # Additional step to modify the navigator.webdriver property
            pages = PlaywrightManager._browser_context.pages
            for page in pages:
                # await stealth_async(page)  # Apply stealth to each page
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """)

        except Exception as e:
            if "Target page, context or browser has been closed" in str(e):
                new_user_dir = tempfile.mkdtemp()
                # logger.error(
                #     f"Failed to launch persistent context with user data dir {user_data_dir}: {e} Trying to launch with a new user dir {new_user_dir}"
                # )
                logger.error(
                    f"Failed to launch persistent context with provided user data dir: {e} Trying to launch with a new user dir {new_user_dir}"
                )
                PlaywrightManager._browser_context = await PlaywrightManager._playwright.chromium.launch_persistent_context(
                    new_user_dir,
                    channel="chrome",
                    headless=self.isheadless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-session-crashed-bubble",  # disable the restore session bubble
                        "--disable-infobars",  # disable informational popups,
                    ],
                    no_viewport=True,
                )
                # # Apply stealth to the new context
                # for page in PlaywrightManager._browser_context.pages:
                #     await stealth_async(page)
            elif "Chromium distribution 'chrome' is not found " in str(e):
                raise ValueError(
                    "Chrome is not installed on this device. Install Google Chrome or install playwright using 'playwright install chrome'. Refer to the readme for more information."
                ) from None
            else:
                raise e from None

    async def get_browser_context(self):
        """
        Returns the existing browser context, or creates a new one if it doesn't exist.
        """
        await self.ensure_browser_context()
        return self._browser_context

    async def get_current_url(self) -> Union[str, None]:
        """
        Get the current URL of current page

        Returns:
            str | None: The current URL if any.
        """
        try:
            current_page: Page = await self.get_current_page()
            return current_page.url
        except Exception:
            pass
        return None

    async def get_current_page(self) -> Page:
        """
        Get the current page of the browser

        Returns:
            Page: The current page if any.
        """
        try:
            browser: BrowserContext = await self.get_browser_context()  # type: ignore
            # Filter out closed pages
            pages: List[Page] = [page for page in browser.pages if not page.is_closed()]
            page: Union[Page, None] = pages[-1] if pages else None
            logger.debug(f"Current page: {page.url if page else None}")
            if page is not None:
                return page
            else:
                page: Page = await browser.new_page()  # type: ignore
                # await stealth_async(page)  # Apply stealth to the new page
                return page
        except Exception as e:
            logger.warn(f"Browser context was closed. Creating a new one. {e}")
            PlaywrightManager._browser_context = None
            await self.ensure_browser_context()
            return await self.get_current_page()

    async def close_all_tabs(self, keep_first_tab: bool = True):
        """
        Closes all tabs in the browser context, except for the first tab if `keep_first_tab` is set to True.

        Args:
            keep_first_tab (bool, optional): Whether to keep the first tab open. Defaults to True.
        """
        browser_context = await self.get_browser_context()
        pages: List[Page] = browser_context.pages  # type: ignore
        pages_to_close: List[Page] = pages[1:] if keep_first_tab else pages  # type: ignore
        for page in pages_to_close:  # type: ignore
            await page.close()  # type: ignore

    async def close_except_specified_tab(self, page_to_keep: Page):
        """
        Closes all tabs in the browser context, except for the specified tab.

        Args:
            page_to_keep (Page): The Playwright page object representing the tab that should remain open.
        """
        browser_context = await self.get_browser_context()
        for page in browser_context.pages:  # type: ignore
            if page != page_to_keep:  # Check if the current page is not the one to keep
                await page.close()  # type: ignore

    async def go_to_homepage(self):
        page: Page = await PlaywrightManager.get_current_page(self)
        try:
            await page.goto(self._homepage, timeout=10000)  # 10 seconds timeout
        except Exception as e:
            logger.error(f"Failed to navigate to homepage: {e}")
            # implement a retry mechanism here
        try:
            await page.goto(self._homepage, timeout=10000)  # 10 seconds timeout
        except Exception as e:
            logger.error(f"Failed to navigate to homepage: {e}")
            # implement a retry mechanism here

    async def set_navigation_handler(self):
        page: Page = await PlaywrightManager.get_current_page(self)
        page.on("domcontentloaded", self.ui_manager.handle_navigation)  # type: ignore
        page.on("domcontentloaded", handle_navigation_for_mutation_observer)  # type: ignore
        await page.expose_function(
            "dom_mutation_change_detected", dom_mutation_change_detected
        )  # type: ignore

    async def set_overlay_state_handler(self):
        logger.debug("Setting overlay state handler")
        context = await self.get_browser_context()
        await context.expose_function(
            "overlay_state_changed", self.overlay_state_handler
        )  # type: ignore
        await context.expose_function(
            "show_steps_state_changed", self.show_steps_state_handler
        )  # type: ignore

    async def overlay_state_handler(self, is_collapsed: bool):
        page = await self.get_current_page()
        self.ui_manager.update_overlay_state(is_collapsed)
        if not is_collapsed:
            await self.ui_manager.update_overlay_chat_history(page)

    async def show_steps_state_handler(self, show_details: bool):
        page = await self.get_current_page()
        await self.ui_manager.update_overlay_show_details(show_details, page)

    async def set_user_response_handler(self):
        context = await self.get_browser_context()
        await context.expose_function("user_response", self.receive_user_response)  # type: ignore

    # async def notify_user(
    #     self, message: str, message_type: MessageType = MessageType.STEP
    # ):
    #     """
    #     Notify the user with a message.

    #     Args:
    #         message (str): The message to notify the user with.
    #         message_type (enum, optional): Values can be 'PLAN', 'QUESTION', 'ANSWER', 'INFO', 'STEP'. Defaults to 'STEP'.
    #         To Do: Convert to Enum.
    #     """

    #     if message.startswith(":"):
    #         message = message[1:]

    #     if message.endswith(","):
    #         message = message[:-1]

    #     if message_type == MessageType.PLAN:
    #         message = beautify_plan_message(message)
    #         message = "Plan:\n" + message
    #     elif message_type == MessageType.STEP:
    #         if "confirm" in message.lower():
    #             message = "Verify: " + message
    #         else:
    #             message = "Next step: " + message
    #     elif message_type == MessageType.QUESTION:
    #         message = "Question: " + message
    #     elif message_type == MessageType.ANSWER:
    #         message = "Response: " + message

    #     safe_message = escape_js_message(message)
    #     self.ui_manager.new_system_message(safe_message, message_type)

    #     if self.ui_manager.overlay_show_details == False:  # noqa: E712
    #         if message_type not in (
    #             MessageType.PLAN,
    #             MessageType.QUESTION,
    #             MessageType.ANSWER,
    #             MessageType.INFO,
    #         ):
    #             return

    #     if self.ui_manager.overlay_show_details == True:  # noqa: E712
    #         if message_type not in (
    #             MessageType.PLAN,
    #             MessageType.QUESTION,
    #             MessageType.ANSWER,
    #             MessageType.INFO,
    #             MessageType.STEP,
    #         ):
    #             return

    #     safe_message_type = escape_js_message(message_type.value)
    #     try:
    #         js_code = f"addSystemMessage({safe_message}, is_awaiting_user_response=false, message_type={safe_message_type});"
    #         page = await self.get_current_page()
    #         await page.evaluate(js_code)
    #     except Exception as e:
    #         logger.error(
    #             f'Failed to notify user with message "{message}". However, most likey this will work itself out after the page loads: {e}'
    #         )

    #     self.notification_manager.notify(message, message_type.value)

    async def highlight_element(self, selector: str, add_highlight: bool):
        try:
            page: Page = await self.get_current_page()
            if add_highlight:
                # Add the 'agente-ui-automation-highlight' class to the element. This class is used to apply the fading border.
                await page.eval_on_selector(
                    selector,
                    """e => {
                            let originalBorderStyle = e.style.border;
                            e.classList.add('agente-ui-automation-highlight');
                            e.addEventListener('animationend', () => {
                                e.classList.remove('agente-ui-automation-highlight')
                            });}""",
                )
                logger.debug(
                    f"Applied pulsating border to element with selector {selector} to indicate text entry operation"
                )
            else:
                # Remove the 'agente-ui-automation-highlight' class from the element.
                await page.eval_on_selector(
                    selector,
                    "e => e.classList.remove('agente-ui-automation-highlight')",
                )
                logger.debug(
                    f"Removed pulsating border from element with selector {selector} after text entry operation"
                )
        except Exception:
            # This is not significant enough to fail the operation
            pass

    # async def receive_user_response(self, response: str):
    #     self.user_response = response  # Store the response for later use.
    #     logger.debug(f"Received user response to system prompt: {response}")
    #     # Notify event loop that the user's response has been received.
    #     self.user_response_event.set()

    # async def prompt_user(self, message: str) -> str:
    #     """
    #     Prompt the user with a message and wait for a response.

    #     Args:
    #         message (str): The message to prompt the user with.

    #     Returns:
    #         str: The user's response.
    #     """
    #     logger.debug(f'Prompting user with message: "{message}"')
    #     # self.ui_manager.new_system_message(message)

    #     page = await self.get_current_page()

    #     await self.ui_manager.show_overlay(page)
    #     self.log_system_message(
    #         message, MessageType.QUESTION
    #     )  # add the message to history after the overlay is opened to avoid double adding it. add_system_message below will add it

    #     safe_message = escape_js_message(message)

    #     js_code = f"addSystemMessage({safe_message}, is_awaiting_user_response=true, message_type='question');"
    #     await page.evaluate(js_code)

    #     await self.user_response_event.wait()
    #     result = self.user_response
    #     logger.info(f'User prompt reponse to "{message}": {result}')
    #     self.user_response_event.clear()
    #     self.user_response = ""
    #     self.ui_manager.new_user_message(result)
    #     return result

    def set_take_screenshots(self, take_screenshots: bool):
        self._take_screenshots = take_screenshots

    def get_take_screenshots(self):
        return self._take_screenshots

    def set_screenshots_dir(self, screenshots_dir: str):
        self._screenshots_dir = screenshots_dir

    def get_screenshots_dir(self):
        return self._screenshots_dir

    async def take_screenshots(
        self,
        name: str,
        page: Union[Page, None],
        full_page: bool = True,
        include_timestamp: bool = True,
        load_state: str = "domcontentloaded",
        take_snapshot_timeout: int = 5 * 1000,
    ):
        if not self._take_screenshots:
            return
        if page is None:
            page = await self.get_current_page()

        screenshot_name = name

        if include_timestamp:
            screenshot_name = f"{int(time.time_ns())}_{screenshot_name}"
        screenshot_name += ".png"
        screenshot_path = f"{self.get_screenshots_dir()}/{screenshot_name}"
        try:
            await page.wait_for_load_state(
                state=load_state, timeout=take_snapshot_timeout
            )  # type: ignore
            await page.screenshot(
                path=screenshot_path,
                full_page=full_page,
                timeout=take_snapshot_timeout,
                caret="initial",
                scale="device",
            )
            logger.debug(f"Screen shot saved to: {screenshot_path}")
        except Exception as e:
            logger.error(
                f'Failed to take screenshot and save to "{screenshot_path}". Error: {e}'
            )

    def log_user_message(self, message: str):
        """
        Log the user's message.

        Args:
            message (str): The user's message to log.
        """
        self.ui_manager.new_user_message(message)

    def log_system_message(self, message: str, type: MessageType = MessageType.STEP):
        """
        Log a system message.

        Args:
            message (str): The system message to log.
        """
        self.ui_manager.new_system_message(message, type)

    async def update_processing_state(self, processing_state: str):
        """
        Update the processing state of the overlay.

        Args:
            is_processing (str): "init", "processing", "done"
        """
        page = await self.get_current_page()

        await self.ui_manager.update_processing_state(processing_state, page)

    async def command_completed(
        self, command: str, elapsed_time: Union[float, None] = None
    ):
        """
        Notify the overlay that the command has been completed.
        """
        logger.debug(
            f'Command "{command}" has been completed. Focusing on the overlay input if it is open.'
        )
        page = await self.get_current_page()
        await self.ui_manager.command_completed(page, command, elapsed_time)
