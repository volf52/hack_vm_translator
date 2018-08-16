
def valid(line):
    """ Line valid or not? """
    line = line.strip()
    if not line:
        return False
    if line.startswith('//'):
        return False
    return True

def clean_lines(lines):
    lines = [line.strip() for line in lines]
    lines = [line.split('//')[0].strip() for line in lines if valid(line)]
    return lines

def initialization():
    """
    Initialize base addresses.
    """
    return [
        '@256', 'D=A', '@SP', 'M=D',
        '@300', 'D=A', '@LCL', 'M=D',
        '@400', 'D=A', '@ARG', 'M=D',
        '@3000', 'D=A', '@THIS', 'M=D',
        '@3010', 'D=A', '@THAT', 'M=D',
    ]

def process_push_pop(command, arg1, arg2, fname, l_no):
    mapping = {'local':'@LCL', 'argument':'@ARG', 'this':'@THIS','that':'@THAT', 
               'static':16, 'temp' : 5, 'pointer': 3}
    ret = []
    if arg1 == 'constant':
        if command == 'pop':
            raise SyntaxError('Can\'t change memory segment. File {}. Line {}'.format(fname, l_no))
        ret.extend([
            '@{}'.format(arg2),
        ])
    elif arg1 == 'static':
        ret.extend([
            '@{}.{}'.format(fname, arg2) 
        ])
    elif arg1 in ('temp', 'pointer'):
        if int(arg2) > 10:
            raise SyntaxError('Invalid location for segment. File {}. Line {}'.format(fname, l_no))
        ret.extend([
            '@R{}'.format(mapping.get(arg1)+int(arg2))
        ])
    elif arg1 in ('local', 'argument', 'this', 'that'):
        ret.extend([
            mapping.get(arg1), 'D=M', '@{}'.format(arg2), 'A=D+A'
        ])
    else:
        raise SyntaxError('{} is invalid memory segment. File {}. Line {}'.format(arg1, fname, l_no))
    
    if command == 'push':
        if arg1 == 'constant':
            ret.append('D=A')
        else:
            ret.append('D=M')
        ret.extend([
            '@SP', 'A=M', 'M=D', # *SP = *addr
            '@SP', 'M=M+1' # SP++
        ])
    else:
        ret.extend(['D=A', 
            '@R13', 'M=D', # addr stored in R13
            '@SP', 'M=M-1', # SP--
            'A=M', 'D=M', # D = *SP
            '@R13', 'A=M', 'M=D' # *addr = D = *SP
        ])
    
    return ret


def process_arithmetic(command, fname, l_no, bool_count):
    ret = []
    symb = {'add':'+', 'sub':'-', 'and':'&', 'or':'|', 'neg': '-', 'not':'!', 'eq':'JEQ', 'lt':'JLT', 'gt':'JGT'}
    if command not in ('neg', 'not'): # unary operators
        ret.extend([
            '@SP', 'M=M-1', # SP--
            'A=M', 'D=M',          # save for next computation
        ])
    ret.extend([
        '@SP', 'M=M-1', # SP--,
        '@SP', 'A=M'
    ])
    
    if command in ('add', 'sub', 'and', 'or'):
        ret.append('M=M{}D'.format(symb.get(command)))
    elif command in ('neg', 'not'):
        ret.append('M={}M'.format(symb.get(command)))
    elif command in ('eq', 'gt', 'lt'):
        ret.extend([
            'D=M-D',
            '@BOOL_{}'.format(bool_count[0]), # Jump to make M=1 if condition is true
            'D;{}'.format(symb.get(command)), 
            '@SP', 'A=M', 'M=0', '@ENDBOOL_{}'.format(bool_count[0]), '0;JMP', # if above condition is false, M=0
            '(BOOL_{})'.format(bool_count[0]), '@SP', 'A=M', 'M=-1', # if condition is true
            '(ENDBOOL_{})'.format(bool_count[0])
        ])
        bool_count[0] += 1
    else:
        raise SyntaxError('File {}. Line {}'.format(fname, l_no))
    
    ret.extend([
        '@SP', 'M=M+1' # SP++
    ])
    
    return ret

def process_line(line, fname, l_no, bool_count):
    tokens = line.strip().split()
    command = tokens[0]
    
    if len(tokens) == 1:
        if command == 'return':
            pass
        elif command in ('add', 'sub', 'neg', 'eq', 'gt', 'lt', 'and', 'or', 'not'):
            ret = process_arithmetic(command, fname, l_no, bool_count)
        else:
            raise SyntaxError("{} is not a valid command. File {}. Line {}".format(command, fname, l_no))
    
    elif len(tokens) == 2:
        pass
    
    elif len(tokens) == 3:
        if command in ('push', 'pop'):
            ret = process_push_pop(*tokens, fname, l_no)
        else:
            raise SyntaxError("{} is not a valid command. File {}. Line {}".format(command, fname, l_no))
    
    else:
        raise SyntaxError("{} is not a valid command. File {}. Line {}".format(command, fname, l_no))
    
    return ret

def process_file(fname, bool_count):
    with open(fname, 'r+') as f:
        vm_code = clean_lines(f.readlines())
    
    fname = fname.replace('.vm', '').split('/')[-1]
    output = []
    
    output = [x for i, line in enumerate(vm_code) for x in process_line(line, fname, i, bool_count)]
    #for i, line in enumerate(vm_code):
    #    tmp = process_line(line, fname, i, bool_count)
    #    output.extend(tmp)
    return output

def translate_vm_to_asm(inp, outname=None):
    is_dir = False
    if os.path.isdir(inp):
        is_dir = True
        if not outname:
            if inp.endswith('/'):
                inp = inp[:-1]
            outname = '{}.asm'.format(os.path.split(inp)[-1])
            outname = os.path.join(inp, outname)
    else:
        if not outname:
            outname = '{}.asm'.format(os.path.splitext(inp)[0])
    
    
    #output, bool_count = initialization(), [0]  
    output, bool_count = [], [0] 
    # Using singelton list for bool_count to avoid using global within multiple functions. Effect will be the same.
    if is_dir:
        for file in os.listdir(inp):
            pth = os.path.join(inp, file)
            if not os.path.isfile(pth):
                continue
            if os.path.splitext(pth)[-1] != '.vm':
                continue
            with open(pth, 'r+') as f:
                vm_code = clean_lines(f.readlines())
            
            tmp = process_file(pth, bool_count)
            output.extend(tmp)
            
    else:
        output.extend(process_file(inp, bool_count))
    
    output.extend(['(END)', '@END', '0;JMP'])
    out_str = '\n'.join(output)
    with open(outname, 'w') as f:
        f.write(out_str)


if __name__ == "__main__":
    import argparse
    import os
    import sys

    parser = argparse.ArgumentParser(
        description="Enter path of directory or file to translate")
    
    parser.add_argument('filename', action="store")
    parser.add_argument('-o', '--outfile' , action="store", default=None, dest='outname')
    args = parser.parse_args()
    fname = args.filename
    outname = args.outname
    if not os.path.exists(fname):
        print("Path doesn't exist")
        sys.exit()
    
    translate_vm_to_asm(fname, outname)
    print("File translated...\nHave fun.")
    