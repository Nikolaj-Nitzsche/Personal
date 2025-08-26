from qcodes import VisaInstrument, validators as vals
from qcodes.utils.helpers import create_on_off_val_mapping


class SMA100B(VisaInstrument):
    """
    This is the qcodes driver for the Rohde & Schwarz SMA100B signal generator
    Status: beta-version.
    .. todo::
        - Add all parameters that are in the manual
        - Add test suite
        - See if there can be a common driver for RS mw sources from which
          different models inherit
    This driver will most likely work for multiple Rohde & Schwarz sources.
    it would be a good idea to group all similar RS drivers together in one
    module.
    Tested working with
    - RS_SMA100B
    This driver does not contain all commands available for the RS_SMA100B but
    only the ones most commonly used.
    """

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, terminator='\n', **kwargs)
        ## RF Output
        self.add_parameter(name='frequency',
                           label='Frequency',
                           unit='Hz',
                           get_cmd='SOUR:FREQ?',
                           set_cmd='SOUR:FREQ {:.2f}',
                           get_parser=float,
                           vals=vals.Numbers(8e3, 20e9))
        self.add_parameter(name='phase',
                           label='Phase',
                           unit='deg',
                           get_cmd='SOUR:PHAS?',
                           set_cmd='SOUR:PHAS {:.2f}',
                           get_parser=float,
                           vals=vals.Numbers(0, 360))
        self.add_parameter(name='power',
                           label='Power',
                           unit='dBm',
                           get_cmd='SOUR:POW?',
                           set_cmd='SOUR:POW {:.2f}',
                           get_parser=float,
                           vals=vals.Numbers(-120, 25))
        self.add_parameter('status',
                           label='RF Output',
                           get_cmd='OUTP:STAT?',
                           set_cmd='OUTP:STAT {}',
                           val_mapping=create_on_off_val_mapping(on_val='1',
                                                                 off_val='0'))
        ## Clock synthesizer output
        self.add_parameter(name='clk_output',
                           label='CLK Output type',
                           get_cmd='CSYN:OTYP?',
                           set_cmd='CSYN:OTYP {}',
                           vals=vals.Enum('SES', 'DSI', 'DSQ', 'CMOS'))
        self.add_parameter(name='clk_dc_offset',
                           label='CLK DC OFFSET',
                           unit='V',
                           get_cmd='CSYNthesis:OFFSet?',
                           set_cmd='CSYNthesis:OFFSet {}',
                           vals=vals.Numbers(-2, 2))        
        self.add_parameter(name='clk_dc_offset_status',
                           label='CLK DC OFFSET STATUS',
                           get_cmd='CSYNthesis:OFFSet:STATe?',
                           set_cmd='CSYNthesis:OFFSet:STATe {}',
                           val_mapping=create_on_off_val_mapping(on_val='1',
                                                                 off_val='0'))          
        self.add_parameter(name='clk_frequency',
                           label='CLK Frequency',
                           unit='Hz',
                           get_cmd='CSYN:FREQ?',
                           set_cmd='CSYN:FREQ {:.2f}',
                           get_parser=float,
                           vals=vals.Numbers(100e3, 3e9))
        self.add_parameter(name='clk_power',
                           label='CLK Power',
                           unit='dBm',
                           get_cmd='CSYN:POW?',
                           set_cmd='CSYN:POW {:.2f}',
                           get_parser=float,
                           vals=vals.Numbers(-24, 20))
        self.add_parameter('clk_status',
                           label='CLK Output',
                           get_cmd='CSYN:STAT?',
                           set_cmd='CSYN:STAT {}',
                           val_mapping=create_on_off_val_mapping(on_val='1',
                                                                 off_val='0'))
        ## Reference clock output
        self.add_parameter(name='ref_output',
                           label='REF Output',
                           get_cmd='SOURce:ROSCillator:OUTPut:FREQuency:MODE?',
                           set_cmd='SOURce:ROSCillator:OUTPut:FREQuency:MODE {}',
                           vals=vals.Enum('DER10M', 'OFF'))
        self.add_parameter(name='ref_source',
                           label='REF Source',
                           get_cmd='SOURce:ROSCillator:SOURce?',
                           set_cmd='SOURce:ROSCillator:SOURce {}',
                           vals=vals.Enum('INT', 'EXT'))   
        ## Pulse modulation output
        self.add_parameter('pulm_status',
                           label='Pulse modulation Output',
                           get_cmd='SOUR:PULM:STAT?',
                           set_cmd='SOUR:PULM:STAT {}',
                           val_mapping=create_on_off_val_mapping(on_val='1',
                                                                 off_val='0'))
        self.add_parameter(name='pulm_source',
                           label='Pulse modulation source',
                           set_cmd='SOURce:PULM:SOURce {}',
                           vals=vals.Enum('INT', 'EXT'))
        self.add_parameter(name='pulm_transition',
                           label='Pulse modulation transition type',
                           set_cmd='SOURce:PULM:TTYP {}',
                           vals=vals.Enum('SMO', 'FAST'))
        self.add_parameter(name='pulm_polarity',
                           label='Pulse modulation video polarity',
                           set_cmd='SOUR:PULM:OUTP:VID:POL {}',
                           vals=vals.Enum('NORM', 'INV'))
        self.add_function('reset', call_cmd='*RST')
        self.add_function('run_self_tests', call_cmd='*TST?')
        self.connect_message()

    def on(self):
        self.status('on')

    def off(self):
        self.status('off')