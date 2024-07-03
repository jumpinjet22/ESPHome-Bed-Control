# ESPHome-Bed-Control
 ___Adjustable Bed Base Integration with Home Assistant___

## Overview
I've been working on integrating my adjustable bed base into Home Assistant. While I have a plan of action, I am reaching the limits of my technical knowledge and venturing into uncharted waters.

## Project Description
This project involves an adjustable base that uses a Keeson MC122SP controller. Through research and forum discussions, I discovered that this base is equipped with an nRF51802 from Nordic Semiconductor. The controller features several multipurpose ports, one of which is intended for syncing two bases. I am attempting to use this port to control the bed.

## Progress
I used a sync cable, which I modified by cutting off the end, to test the signals using a multimeter and an oscilloscope. The signals I captured appear to be digital, and I suspect they might be UART, although I am not entirely certain.

I think I have made steps forward. I noticed that certain bits turned to 1 when I pressed different buttons on the remote. I believe I have found the primary signaling for the remote, but I'm still unsure if this is UART or some proprietary protocol they developed. The question I am asking myself is, would they use a standard that already exists or create their own signaling to communicate between bases?

## Screenshots of Signal
Here are some screenshots I took of the signal:

***no interaction***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00001.png)

***massage head***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00002.png)

***massage timer***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00003.png)

***massage foot***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00004.png)

***Head up***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00005.png)

***Light***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00006.png)

***Foot Up***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00007.png)

***Head Down***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00008.png)

***Zero G***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00009.png)

***Foot Down***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00010.png)

***Preset one***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00011.png)

***Preset two***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00012.png)

***Preset three***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00013.png)

***Unkoown***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00014.png)

***Flatten***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00015.png)

## Next Steps
1. Confirm Signal Type: Determine if the signal is indeed UART.
2. Interface with Home Assistant: Develop a way to interface this signal with Home Assistant.
3. Control Bed: Create a reliable method to control the bed using Home Assistant.


## Conclusion
This project is still a work in progress. If anyone has experience with similar integrations or insights into working with UART signals, your help would be greatly appreciated.

## Contribution
Feel free to open issues or submit pull requests if you have suggestions or improvements.



