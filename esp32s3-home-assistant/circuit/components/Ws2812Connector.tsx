/**
 * WS2812 12-Pixel Addressable LED Ring Connector
 * 
 * 3-pin connector (JST-XH or 2.54mm pin header)
 * with 330Ω protection resistor (R_LED) and 470µF bulk capacitor (C_BULK)
 * 
 * Pin 1: 5V Power
 * Pin 2: DIN (Data In <- 330Ω <- GPIO 4)
 * Pin 3: GND
 */

export interface Ws2812ConnectorProps {
  name?: string;
  pcbX?: number | string;
  pcbY?: number | string;
  pcbRotation?: number | string;
  schX?: number;
  schY?: number;
  schSectionName?: string;
  schSheetName?: string;
}

export const Ws2812Connector = ({
  name = "J_LEDRING",
  pcbX = 0,
  pcbY = 0,
  pcbRotation = "90deg",
  schX = 0,
  schY = 0,
  schSectionName,
  schSheetName,
}: Ws2812ConnectorProps) => {
  return (
    <group name={name} pcbX={pcbX} pcbY={pcbY} schX={schX} schY={schY}>
      <jumper
        name="CONN"
        footprint="pinrow3"
        pcbX="0mm"
        pcbY="0mm"
        pcbRotation={pcbRotation}
        schX={-0.6}
        schY={0}
        schSectionName={schSectionName}
        schSheetName={schSheetName}
        pinLabels={{
          pin1: "5V",
          pin2: "DIN",
          pin3: "GND",
        }}
      />
      <resistor
        name="R_PROT"
        resistance="330"
        footprint="0805"
        pcbX="0mm"
        pcbY="-6.5mm"
        pcbRotation={pcbRotation}
        schX={3.1}
        schY={0}
        schSectionName={schSectionName}
        schSheetName={schSheetName}
      />
    </group>
  );
};
