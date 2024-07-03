# ESPHome-Bed-Control
 ___Adjustable Bed Base Integration with Home Assistant___

## Overview
I've been working on integrating my adjustable bed base into Home Assistant. While I have a plan of action, I am reaching the limits of my technical knowledge and venturing into uncharted waters.

## Project Description
This project involves an adjustable base that uses a Keeson MC122SP controller. Through research and forum discussions, I discovered that this base is equipped with an nRF51802 from Nordic Semiconductor. The controller features several multipurpose ports, one of which is intended for syncing two bases. I am attempting to use this port to control the bed.

## Progress
I used a sync cable, which I modified by cutting off the end, to test the signals using a multimeter and an oscilloscope. The signals I captured appear to be digital, and I suspect they might be UART, although I am not entirely certain.

## Screenshots of Signal
Here are some screenshots I took of the signal:



## Next Steps
1. Confirm Signal Type: Determine if the signal is indeed UART.
2. Interface with Home Assistant: Develop a way to interface this signal with Home Assistant.
3. Control Bed: Create a reliable method to control the bed using Home Assistant.


## Conclusion
This project is still a work in progress. If anyone has experience with similar integrations or insights into working with UART signals, your help would be greatly appreciated.

## Contribution
Feel free to open issues or submit pull requests if you have suggestions or improvements.



