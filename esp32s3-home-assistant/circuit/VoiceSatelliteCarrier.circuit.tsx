import { Esp32S3DevKit } from "./components/Esp32S3DevKit";
import { Inmp441Mic } from "./components/Inmp441Mic";
import { Max98357aAmp } from "./components/Max98357aAmp";
import { Ssd1306Oled } from "./components/Ssd1306Oled";
import { Ws2812Connector } from "./components/Ws2812Connector";

/**
 * ESP32-S3 Home Assistant Voice Satellite — 50x70mm carrier PCB
 * 
 * Target Board: custom double-sided FR4 carrier for socketed breakout modules
 * Mounting: 4x M3 / 3.2mm corner holes spaced at ±21.5mm, ±31.5mm
 */

export const VoiceSatelliteCarrier = () => {
  return (
    <board
      width="50mm"
      height="70mm"
      autorouter="auto-local"
      defaultTraceWidth="0.35mm"
      minTraceWidth="0.25mm"
    >
      <schematicsheet name="Main" displayName="Voice Satellite Carrier" />
      <schematicsection name="MCU" displayName="ESP32-S3 DevKit" />
      <schematicsection name="Audio" displayName="I2S Audio" />
      <schematicsection name="UserIO" displayName="Display and Status Ring" />
      <schematicsection name="Power" displayName="Power Selection and Decoupling" />

      {/* 4x Corner Mechanical Mounting Holes (M3 / 3.2mm) */}
      <hole pcbX="-21.5mm" pcbY="31.5mm" diameter="3.2mm" />
      <hole pcbX="21.5mm" pcbY="31.5mm" diameter="3.2mm" />
      <hole pcbX="-21.5mm" pcbY="-31.5mm" diameter="3.2mm" />
      <hole pcbX="21.5mm" pcbY="-31.5mm" diameter="3.2mm" />

      {/* 1. ESP32-S3 DevKitC-1 Dual Vertical Sockets (Center, X=±12.7mm) */}
      <Esp32S3DevKit name="U_ESP32" pcbX="0mm" pcbY="0mm" schX={0} schY={0} schSectionName="MCU" schSheetName="Main" />

      {/* 2. Round 14mm INMP441 socket; module intentionally overhangs left edge. */}
      <Inmp441Mic name="J_MIC" pcbX="-21.3mm" pcbY="15mm" pcbRotation="90deg" schX={9} schY={2} schSectionName="Audio" schSheetName="Main" />

      {/* 3. MAX98357A I2S DAC Amplifier Socket + Speaker Out (Top-Right) */}
      <Max98357aAmp name="U_AMP" pcbX="19mm" pcbY="15mm" pcbRotation="90deg" schX={9} schY={-2} schSectionName="Audio" schSheetName="Main" />

      {/* 4. SSD1306 I2C OLED Display Socket (Bottom-Left) */}
      <Ssd1306Oled name="J_OLED" pcbX="-19mm" pcbY="-15mm" pcbRotation="90deg" schX={18} schY={2} schSectionName="UserIO" schSheetName="Main" />

      {/* 5. WS2812 12-Pixel LED Ring Header + 330Ω Resistor (Bottom-Right) */}
      <Ws2812Connector name="J_LEDRING" pcbX="19mm" pcbY="-15mm" pcbRotation="90deg" schX={18} schY={-2} schSectionName="UserIO" schSheetName="Main" />

      {/* 6. Optional external 5V peripheral supply (never feeds the DevKit). */}
      <jumper
        name="J_PWR"
        footprint="pinrow2"
        pcbX="-7.5mm"
        pcbY="-31mm"
        pcbRotation="0deg"
        schX={-1}
        schY={-9}
        schSectionName="Power"
        schSheetName="Main"
        pinLabels={{
          pin1: "EXT_5V",
          pin2: "GND",
        }}
      />

      {/*
       * Install exactly one 2-pin shunt:
       *   pins 1-2: DevKit/USB 5V powers the peripherals
       *   pins 2-3: external 5V powers the peripherals
       * External mode deliberately leaves the DevKit on its own USB supply,
       * preventing an external supply from back-feeding either USB connector.
       */}
      <jumper
        name="J_PWR_SEL"
        footprint="pinrow3"
        pcbX="0mm"
        pcbY="-30mm"
        schX={3.1}
        schY={-8.42}
        schSectionName="Power"
        schSheetName="Main"
        pinLabels={{
          pin1: "DEVKIT_5V",
          pin2: "PERIPH_5V",
          pin3: "EXT_5V",
        }}
      />

      {/* 7. Decoupling & Bulk Capacitors */}
      {/* 470µF Bulk capacitor across 5V rail */}
      <capacitor
        name="C_BULK_5V"
        capacitance="470uF"
        footprint="electrolytic_d6.3mm_p2.5mm"
        pcbX="8mm"
        pcbY="-31.5mm"
        schX={7}
        schY={-9}
        schOrientation="vertical"
        schSectionName="Power"
        schSheetName="Main"
      />

      {/* 10µF 3.3V Decoupling capacitor */}
      <capacitor
        name="C_3V3_1"
        capacitance="10uF"
        footprint="0805"
        pcbX="-19mm"
        pcbY="0mm"
        schX={9}
        schY={-9}
        schOrientation="vertical"
        schSectionName="Power"
        schSheetName="Main"
      />

      {/* 0.1µF High-Frequency Decoupling capacitor */}
      <capacitor
        name="C_3V3_2"
        capacitance="0.1uF"
        footprint="0805"
        pcbX="-19mm"
        pcbY="-5mm"
        schX={11.5}
        schY={-9}
        schOrientation="vertical"
        schSectionName="Power"
        schSheetName="Main"
      />

      {/* ==================== TRACE / SOLDER WIRE ROUTING ==================== */}

      {/* --- I2C Bus for SSD1306 OLED --- */}
      <trace name="T_I2C_SCL" from=".U_ESP32 > .J_LEFT > .GPIO5" to=".J_OLED > .SCL" />
      <trace name="T_I2C_SDA" from=".U_ESP32 > .J_LEFT > .GPIO6" to=".J_OLED > .SDA" />

      {/* --- I2S Microphone Bus (INMP441) --- */}
      <trace name="T_MIC_SD" from=".U_ESP32 > .J_LEFT > .GPIO7" to=".J_MIC > .SD" />
      <trace name="T_MIC_SCK" from=".U_ESP32 > .J_LEFT > .GPIO15" to=".J_MIC > .SCK" />
      <trace name="T_MIC_WS" from=".U_ESP32 > .J_LEFT > .GPIO16" to=".J_MIC > .WS" />

      {/* --- I2S Audio Speaker Bus (MAX98357A) --- */}
      <trace name="T_AMP_BCLK" from=".U_ESP32 > .J_LEFT > .GPIO17" to=".U_AMP > .J_HEADER > .BCLK" />
      <trace name="T_AMP_LRC" from=".U_ESP32 > .J_LEFT > .GPIO18" to=".U_AMP > .J_HEADER > .LRC" />
      <trace name="T_AMP_DIN" from=".U_ESP32 > .J_LEFT > .GPIO8" to=".U_AMP > .J_HEADER > .DIN" />

      {/* --- WS2812 LED Ring Data --- */}
      <trace name="T_LED_GPIO4" from=".U_ESP32 > .J_LEFT > .GPIO4" to=".J_LEDRING > .R_PROT > .pin1" />
      <trace name="T_LED_DIN" from=".J_LEDRING > .R_PROT > .pin2" to=".J_LEDRING > .CONN > .DIN" />

      {/* --- 3.3V Power Rail (V3V3) --- */}
      <trace name="T_3V3_ESP" from=".U_ESP32 > .J_LEFT > .3V3_1" to="net.V3V3" thickness="0.5mm" />
      <trace name="T_3V3_MIC" from=".J_MIC > .VDD" to="net.V3V3" thickness="0.5mm" />
      <trace name="T_3V3_OLED" from=".J_OLED > .VCC" to="net.V3V3" thickness="0.5mm" />
      <trace name="T_3V3_C1" from=".C_3V3_1 > .pin1" to="net.V3V3" thickness="0.5mm" />
      <trace name="T_3V3_C2" from=".C_3V3_2 > .pin1" to="net.V3V3" thickness="0.5mm" />

      {/* --- 5V Power Rail (V5V) --- */}
      <trace name="T_5V_DEVKIT_SEL" from=".U_ESP32 > .J_LEFT > .5V" to=".J_PWR_SEL > .pin1" thickness="1mm" />
      <trace name="T_5V_PERIPH_SEL" from=".J_PWR_SEL > .pin2" to="net.V5V" thickness="1mm" />
      <trace name="T_5V_EXT_SEL" from=".J_PWR > .pin1" to=".J_PWR_SEL > .pin3" thickness="1mm" />
      <trace name="T_5V_AMP" from=".U_AMP > .J_HEADER > .VIN" to="net.V5V" thickness="1mm" />
      <trace name="T_5V_LED" from=".J_LEDRING > .CONN > .5V" to="net.V5V" thickness="1mm" />
      <trace name="T_5V_CBULK" from=".C_BULK_5V > .pin1" to="net.V5V" thickness="1mm" />

      {/* --- Ground Rail (GND) --- */}
      <trace name="T_GND_ESP1" from=".U_ESP32 > .J_RIGHT > .GND_1" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_ESP2" from=".U_ESP32 > .J_RIGHT > .GND_2" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_ESP3" from=".U_ESP32 > .J_RIGHT > .GND_3" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_ESP4" from=".U_ESP32 > .J_LEFT > .GND" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_MIC1" from=".J_MIC > .GND" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_MIC2" from=".J_MIC > .L_R" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_AMP1" from=".U_AMP > .J_HEADER > .GND" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_AMP2" from=".U_AMP > .J_HEADER > .GAIN" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_OLED" from=".J_OLED > .GND" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_LED" from=".J_LEDRING > .CONN > .GND" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_CBULK" from=".C_BULK_5V > .pin2" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_C1" from=".C_3V3_1 > .pin2" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_C2" from=".C_3V3_2 > .pin2" to="net.GND" thickness="0.8mm" />
      <trace name="T_GND_PWR" from=".J_PWR > .pin2" to="net.GND" thickness="0.8mm" />
    </board>
  );
};

export default VoiceSatelliteCarrier;
