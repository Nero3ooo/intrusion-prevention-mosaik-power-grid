# component.py
# by Verena
# Version 0.1
'''
Component class 
This is the basic class from which all virtual components inherit. 
'''


class component():
    '''
    Component super class
    '''
    def __init__(self, name):
        self.id = name
        pass

    def get_name(self):
        '''Returns the name of the component'''
        return self.id