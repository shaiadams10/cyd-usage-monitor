/**
 * ESP32-S3 DevKitC-1 Socket Header Pair
 * 
 * Official ESP32-S3-DevKitC-1 v1.0/v1.1 44-pin header mapping.
 * The 2x22 female sockets use 2.54 mm pitch and 25.4 mm row spacing.
 *
 * IMPORTANT: keep this mapping aligned with Espressif's J1/J3 tables. The 5 V
 * pin is J1 pin 21; J3 pins 21 and 22 are both ground.
 */

export interface Esp32S3DevKitProps {
  name?: string;
  pcbX?: number | string;
  pcbY?: number | string;
  schX?: number;
  schY?: number;
  schSectionName?: string;
  schSheetName?: string;
}

export const Esp32S3DevKit = ({
  name = "U_ESP32",
  pcbX = 0,
  pcbY = 0,
  schX = 0,
  schY = 0,
  schSectionName,
  schSheetName,
}: Esp32S3DevKitProps) => {
  return (
    <group name={name} pcbX={pcbX} pcbY={pcbY} schX={schX} schY={schY}>
      {/* Left 22-pin vertical header socket */}
      <jumper
        name="J_LEFT"
        footprint="pinrow22"
        pcbX="-11.43mm"
        pcbY="0mm"
        pcbRotation="90deg"
        schX={-2.1}
        schY={0}
        schWidth="1.67mm"
        schSectionName={schSectionName}
        schSheetName={schSheetName}
        pinLabels={{
          pin1: "3V3_1",
          pin2: "3V3_2",
          pin3: "EN",
          pin4: "GPIO4",
          pin5: "GPIO5",
          pin6: "GPIO6",
          pin7: "GPIO7",
          pin8: "GPIO15",
          pin9: "GPIO16",
          pin10: "GPIO17",
          pin11: "GPIO18",
          pin12: "GPIO8",
          pin13: "GPIO3",
          pin14: "GPIO46",
          pin15: "GPIO9",
          pin16: "GPIO10",
          pin17: "GPIO11",
          pin18: "GPIO12",
          pin19: "GPIO13",
          pin20: "GPIO14",
          pin21: "5V",
          pin22: "GND",
        }}
      />

      {/* Right 22-pin vertical header socket */}
      <jumper
        name="J_RIGHT"
        footprint="pinrow22"
        pcbX="11.43mm"
        pcbY="0mm"
        pcbRotation="90deg"
        schX={2.1}
        schY={0}
        schWidth="1.67mm"
        schSectionName={schSectionName}
        schSheetName={schSheetName}
        pinLabels={{
          pin1: "GND_1",
          pin2: "GPIO43",
          pin3: "GPIO44",
          pin4: "GPIO1",
          pin5: "GPIO2",
          pin6: "GPIO42",
          pin7: "GPIO41",
          pin8: "GPIO40",
          pin9: "GPIO39",
          pin10: "GPIO38",
          pin11: "GPIO37",
          pin12: "GPIO36",
          pin13: "GPIO35",
          pin14: "GPIO0",
          pin15: "GPIO45",
          pin16: "GPIO48",
          pin17: "GPIO47",
          pin18: "GPIO21",
          pin19: "GPIO20",
          pin20: "GPIO19",
          pin21: "GND_2",
          pin22: "GND_3",
        }}
      />
      <silkscreenrect
        pcbX="0mm"
        pcbY="0mm"
        width="25.4mm"
        height="62.74mm"
        filled={false}
        stroke="solid"
        strokeWidth="0.2mm"
      />
    </group>
  );
};
