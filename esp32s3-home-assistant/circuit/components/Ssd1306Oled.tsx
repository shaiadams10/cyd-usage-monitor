/**
 * SSD1306 0.96" / 1.3" I2C Monochrome OLED Display Socket
 * 
 * 4-pin female header (2.54mm pitch)
 * Pin 1: GND
 * Pin 2: VCC (3.3V power rail)
 * Pin 3: SCL (I2C Clock -> GPIO 5)
 * Pin 4: SDA (I2C Data  -> GPIO 6)
 */

export interface Ssd1306OledProps {
  name?: string;
  pcbX?: number | string;
  pcbY?: number | string;
  pcbRotation?: number | string;
  schX?: number;
  schY?: number;
  schSectionName?: string;
  schSheetName?: string;
}

export const Ssd1306Oled = ({
  name = "J_OLED",
  pcbX = 0,
  pcbY = 0,
  pcbRotation = "90deg",
  schX = 0,
  schY = 0,
  schSectionName,
  schSheetName,
}: Ssd1306OledProps) => {
  return (
    <jumper
      name={name}
      footprint="pinrow4"
      pcbX={pcbX}
      pcbY={pcbY}
      pcbRotation={pcbRotation}
      schX={schX}
      schY={schY}
      schWidth="1.38mm"
      schSectionName={schSectionName}
      schSheetName={schSheetName}
      pinLabels={{
        pin1: "GND",
        pin2: "VCC",
        pin3: "SCL",
        pin4: "SDA",
      }}
    />
  );
};
