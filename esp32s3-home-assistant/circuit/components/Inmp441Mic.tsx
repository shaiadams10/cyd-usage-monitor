/**
 * HZWDONE round INMP441 Omnidirectional I2S MEMS Microphone Socket
 * 
 * The purchased module is a 14mm round board with two three-pin rows. Each row
 * is 2.54mm pitch and the row centers are 5.08mm apart. Viewed from the labeled
 * face with the acoustic-port arrow pointing right, the pads are:
 *
 *   SD   VDD  GND
 *   L/R  WS   SCK
 *
 * The carrier uses female sockets so the module remains replaceable.
 */

export interface Inmp441MicProps {
  name?: string;
  pcbX?: number | string;
  pcbY?: number | string;
  pcbRotation?: number | string;
  schX?: number;
  schY?: number;
  schSectionName?: string;
  schSheetName?: string;
}

export const Inmp441Mic = ({
  name = "J_MIC",
  pcbX = 0,
  pcbY = 0,
  pcbRotation = "90deg",
  schX = 0,
  schY = 0,
  schSectionName,
  schSheetName,
}: Inmp441MicProps) => {
  return (
    <jumper
      name={name}
      footprint={
        <footprint insertionDirection="from_above">
          <platedhole portHints={["pin3"]} pcbX="-2.54mm" pcbY="2.54mm" shape="circle" holeDiameter="1mm" outerDiameter="1.8mm" />
          <platedhole portHints={["pin1"]} pcbX="0mm" pcbY="2.54mm" shape="circle" holeDiameter="1mm" outerDiameter="1.8mm" />
          <platedhole portHints={["pin2"]} pcbX="2.54mm" pcbY="2.54mm" shape="circle" holeDiameter="1mm" outerDiameter="1.8mm" />
          <platedhole portHints={["pin4"]} pcbX="-2.54mm" pcbY="-2.54mm" shape="circle" holeDiameter="1mm" outerDiameter="1.8mm" />
          <platedhole portHints={["pin5"]} pcbX="0mm" pcbY="-2.54mm" shape="circle" holeDiameter="1mm" outerDiameter="1.8mm" />
          <platedhole portHints={["pin6"]} pcbX="2.54mm" pcbY="-2.54mm" shape="circle" holeDiameter="1mm" outerDiameter="1.8mm" />
          <silkscreencircle pcbX="0mm" pcbY="0mm" radius="7mm" strokeWidth="0.2mm" />
          <courtyardcircle pcbX="0mm" pcbY="0mm" radius="7.25mm" />
        </footprint>
      }
      pcbX={pcbX}
      pcbY={pcbY}
      pcbRotation={pcbRotation}
      schX={schX}
      schY={schY}
      schWidth="1.38mm"
      schSectionName={schSectionName}
      schSheetName={schSheetName}
      pinLabels={{
        pin1: "VDD",
        pin2: "GND",
        pin3: "SD",
        pin4: "L_R",
        pin5: "WS",
        pin6: "SCK",
      }}
    />
  );
};
