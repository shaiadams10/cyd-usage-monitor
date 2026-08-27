/**
 * MAX98357A I2S 3W Mono Class D DAC Amplifier Socket
 * 
 * 7-pin female header (2.54mm pitch). The speaker connects to the bridge-tied
 * output terminal on the MAX98357A breakout itself; neither speaker lead is
 * ground and the carrier must not add an unconnected duplicate terminal.
 * Pin 1: LRC  (I2S Word Select -> GPIO 18)
 * Pin 2: BCLK (I2S Bit Clock   -> GPIO 17)
 * Pin 3: DIN  (I2S Serial Data -> GPIO 8)
 * Pin 4: GAIN (Gain strap: GND = +12dB)
 * Pin 5: SD   (Shutdown/channel: floating or pullup)
 * Pin 6: GND  (Power & signal ground)
 * Pin 7: VIN  (5V power supply)
 */

export interface Max98357aAmpProps {
  name?: string;
  pcbX?: number | string;
  pcbY?: number | string;
  pcbRotation?: number | string;
  schX?: number;
  schY?: number;
  schSectionName?: string;
  schSheetName?: string;
}

export const Max98357aAmp = ({
  name = "U_AMP",
  pcbX = 0,
  pcbY = 0,
  pcbRotation = "90deg",
  schX = 0,
  schY = 0,
  schSectionName,
  schSheetName,
}: Max98357aAmpProps) => {
  return (
    <group name={name} pcbX={pcbX} pcbY={pcbY} schX={schX} schY={schY}>
      <jumper
        name="J_HEADER"
        footprint="pinrow7"
        pcbX="0mm"
        pcbY="0mm"
        pcbRotation={pcbRotation}
        schWidth="1.76mm"
        schSectionName={schSectionName}
        schSheetName={schSheetName}
        pinLabels={{
          pin1: "LRC",
          pin2: "BCLK",
          pin3: "DIN",
          pin4: "GAIN",
          pin5: "SD_MODE",
          pin6: "GND",
          pin7: "VIN",
        }}
      />
    </group>
  );
};
