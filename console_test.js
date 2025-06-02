(function() {
    console.log("Vexa Speaker Event Logger: Initializing...");

    // --- Configuration ---
    const participantSelector = '.IisKdb'; // Main selector for participant container/element
    const speakingClass = 'gjg47c';       // Class indicating the participant is speaking
    const nameSelectors = [               // Try these selectors to find the participant's name
        '.zWGUib',                        // Common name display class in Google Meet
        '.XWGOtd',                        // Another potential name class
        '[data-self-name]',               // Attribute often holding self name
        '[data-participant-id]'           // Attribute for participant ID (can be used if name not found)
    ];
    const checkInterval = 500; // ms - How often to rescan for new participants if observer misses some dynamic loads

    // --- State ---
    const speakingStates = new Map(); // Stores the speaking state (true/false) for each participant ID/element

    // --- Helper Functions ---
    function getParticipantId(element) {
        // Try to get a unique ID, fallback to a generated one if necessary
        let id = element.getAttribute('data-participant-id');
        if (!id) {
            // If no data-participant-id, try to find a more stable child for ID
            const stableChild = element.querySelector('[jsinstance]');
            if (stableChild) {
                id = stableChild.getAttribute('jsinstance');
            }
        }
        if (!id) {
            if (!element.dataset.vexaGeneratedId) {
                element.dataset.vexaGeneratedId = 'vexa-id-' + Math.random().toString(36).substr(2, 9);
            }
            id = element.dataset.vexaGeneratedId;
        }
        return id;
    }

    function getParticipantName(participantElement) {
        for (const selector of nameSelectors) {
            const nameElement = participantElement.querySelector(selector);
            if (nameElement) {
                let nameText = nameElement.textContent || nameElement.innerText || nameElement.getAttribute('data-self-name');
                if (nameText && nameText.trim()) return nameText.trim();
            }
        }
        // Fallback if no specific name element is found but it's the 'You' element
        if (participantElement.textContent && participantElement.textContent.includes("You") && participantElement.textContent.length < 20) {
            return "You";
        }
        // Last fallback: use the participant ID
        return `Participant (${getParticipantId(participantElement)})`;
    }

    function logSpeakerEvent(participantElement, isSpeaking) {
        const participantId = getParticipantId(participantElement);
        const participantName = getParticipantName(participantElement);
        const previousState = speakingStates.get(participantId);

        if (isSpeaking && !previousState) { // Actual START event
            console.log(`%c🎤 ${participantName} started speaking`, 'color: green; font-weight: bold;');
            speakingStates.set(participantId, true);
        } else if (previousState === undefined && isSpeaking) { // Initial detection and is speaking
            console.log(`%c🎤 ${participantName} started speaking (initial detection)`, 'color: blue; font-weight: bold;');
            speakingStates.set(participantId, true);
        } else if (!isSpeaking && previousState) { // Actual STOP event - update state but no log
            speakingStates.set(participantId, false);
        } else if (previousState === undefined && !isSpeaking) { // Initial detection and is not speaking - update state but no log
            speakingStates.set(participantId, false);
        }
        // If isSpeaking is true and previousState is true (still speaking), do nothing to log, state is same.
        // If isSpeaking is false and previousState is false (still not speaking), do nothing to log, state is same.
    }

    // --- Main Logic ---
    function observeParticipant(participantElement) {
        // Initial check
        logSpeakerEvent(participantElement, participantElement.classList.contains(speakingClass));

        // The observer callback
        const callback = function(mutationsList, observer) {
            for (const mutation of mutationsList) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    const targetElement = mutation.target;
                    if (targetElement.matches(participantSelector)) {
                        const isNowSpeaking = targetElement.classList.contains(speakingClass);
                        logSpeakerEvent(targetElement, isNowSpeaking);
                    }
                }
            }
        };

        // Create an observer instance linked to the callback function
        const observer = new MutationObserver(callback);

        // Start observing the target node for configured mutations
        observer.observe(participantElement, { attributes: true, attributeFilter: ['class'] });
        // Store observer for potential cleanup if needed
        if (!participantElement.dataset.vexaObserverAttached) {
             participantElement.dataset.vexaObserverAttached = 'true';
        }
    }

    function scanForAllParticipants() {
        const participantElements = document.querySelectorAll(participantSelector);
        // console.log(`Vexa Speaker Event Logger: Found ${participantElements.length} participant elements.`);
        participantElements.forEach(el => {
            // Check if already observing to avoid duplicates if elements are stable
            // and scanForAllParticipants is called multiple times
            if (!el.dataset.vexaObserverAttached) {
                 observeParticipant(el);
            } else {
                // If already observed, just ensure current state is logged/updated
                // This handles cases where an element might have been missed by mutation but class changed
                const isCurrentlySpeaking = el.classList.contains(speakingClass);
                const participantId = getParticipantId(el);
                if (speakingStates.get(participantId) !== isCurrentlySpeaking) {
                    logSpeakerEvent(el, isCurrentlySpeaking);
                }
            }
        });
    }

    // --- Initialization and Dynamic Handling ---

    // Initial scan
    scanForAllParticipants();

    // Observe the body for new participants being added to the DOM
    // This is a broader observer for dynamically added participant cards
    const bodyObserver = new MutationObserver((mutationsList) => {
        for (const mutation of mutationsList) {
            if (mutation.type === 'childList') {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        const elementNode = node;
                        // Check if the added node itself is a participant
                        if (elementNode.matches(participantSelector) && !elementNode.dataset.vexaObserverAttached) {
                            observeParticipant(elementNode);
                        }
                        // Check if any children of the added node are participants
                        elementNode.querySelectorAll(participantSelector).forEach(childEl => {
                            if (!childEl.dataset.vexaObserverAttached) {
                                observeParticipant(childEl);
                            }
                        });
                    }
                });
                // Also check for removed nodes to clean up map (optional, good practice)
                mutation.removedNodes.forEach(node => {
                     if (node.nodeType === Node.ELEMENT_NODE) {
                        const elementNode = node;
                        if (elementNode.matches(participantSelector)) {
                           speakingStates.delete(getParticipantId(elementNode));
                           delete elementNode.dataset.vexaObserverAttached;
                           delete elementNode.dataset.vexaGeneratedId;
                        }
                        elementNode.querySelectorAll(participantSelector).forEach(childEl => {
                            speakingStates.delete(getParticipantId(childEl));
                            delete childEl.dataset.vexaObserverAttached;
                            delete childEl.dataset.vexaGeneratedId;
                        });
                    }
                });
            }
        }
    });

    // Start observing the document body for additions/removals of participant elements
    // Google Meet can be very dynamic, so observing a high-level parent is often necessary.
    const targetNode = document.body;
    if (targetNode) {
        bodyObserver.observe(targetNode, { childList: true, subtree: true });
        console.log("Vexa Speaker Event Logger: Observing document body for participant changes.");
    } else {
        console.error("Vexa Speaker Event Logger: Could not find document body to observe.");
    }

    // Fallback interval scanning for any missed elements (e.g., if DOM structure changes unexpectedly)
    setInterval(scanForAllParticipants, checkInterval);


    console.log("Vexa Speaker Event Logger: Running. Open console to see speaker events.");
    // To stop: you might need to manually disconnect observers if running this multiple times
    // e.g., by adding a global flag or a function `window.stopVexaLogger = () => { bodyObserver.disconnect(); ... }`
})(); 