#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time    : 2023/12
# @Author  : 
# @FileName: archlabfinal.py
"""
本程序旨在自动生成arch-lab的代码\\
但是这里生成的只是一个粗略的代码，并且最终结果是无法满分的\\
但是可以比较几种展开的CPE，帮助选择一个较为合适的展开。\\
并且本程序的异常处理很弱，所以请使用者自己保证输入的值合理以及自己debug\\
generate函数根据给定展开序列生成ncopy.ys可修改部分\\
Writefile函数则生成ncopy.ys函数(可以结合相应指令快捷查看结果例如`(python3 archlabfinal.py; ./correctness.pl; ./benchmark; ./check-len.pl < ncopy.yo)`)\\
seekBest函数会生成comparison.txt文件，根据函数里面给定的展开序列列表（需自己修改）产生CPE、correct、lenth检查结果\\
（所以请将archlabfinal.py置于sim\pipe下）
"""

mysrc=["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight","Nine","Ten","Eleven"]
registers=["%r8","%r9","%r10","%r11","%r12","%r13","%r14", "%rcx", "%rbx", "%rbp"]

# class code:
def generate(*enrolls:int):
    """
    *enrolls传入参数，如何进行循环展开，例如传入8,4,2,1则是按照8、4、2、1分别展开
    """
    code=""
    for _ in range(0, len(enrolls)):
        pre=0
        next=0
        index = _
        if _==0:
            pre=0
        else:
            pre=enrolls[_-1]
        if _==len(enrolls)-1:
            next=0
        else:
            next=enrolls[_+1]

        # 如果想看看不使用单独处理的单元素循环的情况，可以试着改变条件，看看CPE会增大多少👍
        if enrolls[_]==1:
            code+=produceOneEnrollment(pre=pre)
        else:
            code+=produceLoopHeader(pre=pre, index=enrolls[_], next=next)
            code+=produceLoopBody(index=enrolls[_])
            code+=produceLoopStep(index=enrolls[_])
            code+=produceLoopTail(pre=pre, index=enrolls[_], next=next)
    
    return code

def produceLoopHeader(pre:int=0, index:int=1, next:int=0):
    """
    产生循环头，具体来说根据pre来确定rdx +-多少、以及根据next来决定跳转到哪里
    """
    loopHeader=f"""
{mysrc[index-1]}Enroll:"""
    # pre+index
    if pre==0:
        # pre==0, 只需要-即可
        loopHeader+=f"""
    iaddq ${-index}, %rdx # lenth -={index}"""
    else:
        
        loopHeader+=f"""
    iaddq ${pre-index}, %rdx # lenth += {pre-index}"""
        if pre < index:
            print(f"WARNING! Jump from small to big enrollment({pre} to {index}), it may not work!")
            loopHeader+=f"#WARNING! Jump from small to big enrollment({pre} to {index}), it may not work!"
        
    # jmp, next
    if next==0:
        # 没有后续展开了，跳转到Done
        loopHeader+=f"""
    jl Done # ret
"""
        # 如果index !=1 的话，做出提醒
        # loopHeader+=f"""# WARNING! FINAL LOOP not end with 1!"""
        # print("WARNING! FINAL LOOP not end with 1!")
    else:
        loopHeader+=f"""
    jl {mysrc[next-1]}Enroll # lenth < {index}, jump to {mysrc[next-1]}Enroll
"""
        if next > index:
            loopHeader+=f"#WARNING! Jump from small to big enrollment({index} to {next}), it may not work!"
            print(f"WARNING! Jump from small to big enrollment({index} to {next}), it may not work!")
        
    return loopHeader

def produceLoopBody(index):
    """
    根据给定数字产生值复制部分的代码

    注意 给定的index不能大于寄存器列表长度，太长需要手动写寄存器间的值传递
    因为这里是默认先将所有mr操作做完再做rm操作以减少bubble，index过大则需要自己再写，注意使用相同寄存器时的bubble\\
    对于单个元素(index=1)循环情况下，需要单独考虑以减少冒险！
    """
    loopBody=f"""
{mysrc[index-1]}EnrollLoop:
"""
    #mr操作
    for _ in range(0, index):
        loopBody+=f"""
    mrmovq {8*_}(%rdi), {registers[_]}"""
        
    for _ in range(0, index):
        loopBody+=f"""
    rmmovq {registers[_]}, {8*_}(%rsi)"""
    return loopBody

def produceLoopStep(index):
    """
    这里是对于每个复制的值进行正负判断

    注意正如loopBody中所说的，对index>len(registers)的情况以及index=1的情况需要手动考虑冒险以减少bubble

    不过这里格式看起来可能有点不好理解...先andq在xxEnrollStepxx（主要是最后一个step和前面不一样，需要进行地址加减...），但是整体程序看起来的话是比较容易理解的
    """
    loopStep=""""""
    for step in range(0, index):
        loopStep+=f"""
    andq {registers[step]}, {registers[step]}
    jle {mysrc[index-1]}EnrollStep{mysrc[step]}
    iaddq $1, %rax # >0, count++
{mysrc[index-1]}EnrollStep{mysrc[step]}:
"""
    return loopStep

def produceLoopTail(pre=0, index=1, next=0):
    """
    循环尾部，进行地址加减以及进行跳转，续接step

    这里需要pre是为了根据pre来判断index是否可能进行第二次循环，例如pre=8 index=4，那么这里就不可能有两个4的循环
    
    注意iaddq也是会改变状态码的，不需要额外操作进行判断lenth的正负
    """
    loopTail=""
    # src, dst ++
    loopTail+=f"""
    iaddq ${8*index}, %rdi
    iaddq ${8*index}, %rsi
    iaddq ${-index}, %rdx # neccesary, 因为在循环头部会进行pre-index
"""
    if pre>2*index or pre==0:
        loopTail+=f"""
    jge {mysrc[index-1]}EnrollLoop
"""
    return loopTail
    
def produceOneEnrollment(pre=0):
    """
    对单次循环进行特殊处理，以减少数据冒险，在mr与rm间插入其他操作消除bubble(只需要一条即可)
    
    此外需要pre对lenth进行修正，
    """
    if(pre==1):
        print("Error! 1 to 1 enrollment!\n")
        exit()

    oneEnrollment=""
    if pre > 2 or pre==0: #pre<=2也只会进行一次循环
         oneEnrollment+=f"""
OneEnroll:
    iaddq ${pre-1}, %rdx
    jl Done

OneEnrollLoop:
    mrmovq (%rdi), {registers[0]}
    iaddq $8, %rsi
    iaddq $8, %rdi
    andq {registers[0]}, {registers[0]}
    rmmovq {registers[0]}, -8(%rsi)
    jle Nope
    iaddq $1, %rax
Nope:
    iaddq $-1, %rdx
    jge OneEnrollLoop
"""
    else:
        oneEnrollment+=f"""
OneEnroll:
    iaddq ${pre-1}, %rdx
    jl Done

OneEnrollLoop:
    mrmovq (%rdi), {registers[0]}
    rmmovq {registers[0]}, (%rsi)
    andq {registers[0]}, {registers[0]}
    jle Nope
    iaddq $1, %rax
Nope:
"""
    return oneEnrollment

def Writefile(body, path="./ncopy.ys"):
    """
    本函数是直接生成ncopy.ys文件，然后可以在命令行执行相应正确性检测，以及CPE计算等等。
    
    例如: (python3 archlabfinal.py; ./correctness.pl; ./benchmark; ./check-len.pl < ncopy.yo)
    注意python文件的名字，测试的时候叫这个名字，可能最终不叫这个名字，因为我可能忘记修改这里的注释
    """

    head = f"""
#/* $begin ncopy-ys */
##################################################################
# ncopy.ys - Copy a src block of len words to dst.
# Return the number of positive words (>0) contained in src.
#
# Include your name and ID here.
#
#     name:
#     ID: 
#
# Describe how and why you modified the baseline code.
#
##################################################################
# Do not modify this portion
# Function prologue.
# %rdi = src, %rsi = dst, %rdx = len
ncopy:

##################################################################
# You can modify this portion
# Loop header
"""
    tail = f"""

##################################################################
# Do not modify the following section of code
# Function epilogue.
Done:
	ret
##################################################################
# Keep the following label at the end of your function
End:
#/* $end ncopy-ys */


"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(head+body+tail)

def seekBest():
    import subprocess
    """
    本函数旨是一个自动化执行多个循环组合的脚本。单独测试可以调研writefile函数或generate函数。

    本函数通过遍历给定的循环组合，将benchmark的结果写入result文件，读取最后一行，记录CPE。
    （如果CPE看起来比较可疑，可以手动运行检测一下）
    """
    commands = [
            f"make ncopy.yo",
            "./correctness.pl > correct",
            "./benchmark.pl > result",
            "./check-len.pl < ncopy.yo > lenth"
        ]
    file=open("comparison.txt", 'w', encoding="utf-8")

    # 例子，可以自己修改，自己需要比较的序列，结果会在本文件夹下生成一个comparison.txt文件
    checklist=[[1],[2,1],[3,1]]

    # 这里只是我测试的一些循环组合，这里其实应该程序自动生成的，但是我都已经写了不少了就没写自动生成的了，注意例如10,6,3,2,1这种大概率
    # 就超过1000Bytes了
    # checklist=[[1],[2,1],[3,1],[4,1],[5,1],[6,1],[7,1],[8,1],[9,1],[10,1],[3,2,1],[4,2,1],[4,3,1],[5,2,1],[5,3,1],
    #            [6,2,1],[6,3,1],[6,4,1],[7,2,1],[7,3,1],[7,4,1],[7,5,1],[8,2,1],[8,3,1],[8,4,1],[8,5,1],[8,6,1],
    #            [9,2,1],[9,3,1],[9,4,1],[9,5,1],[9,6,1],[10,2,1],[10,3,1],[10,4,1],[10,5,1],[10,6,1],[4,3,2,1],
    #            [5,3,2,1],[5,4,2,1],[5,4,3,1],[6,3,2,1],[6,4,2,1],[6,4,3,1],[6,5,2,1],[6,5,3,1],[7,3,2,1],[7,4,2,1],
    #            [7,4,3,1],[7,5,2,1],[7,5,3,1],[7,5,4,1],[8,3,2,1],[8,4,2,1],[8,4,3,1],[8,5,3,1],[8,5,2,1],[8,6,3,1],
    #            [8,6,2,1],[9,3,2,1],[9,4,2,1],[9,4,3,1],[9,5,3,1],[9,5,2,1],[9,6,3,1],[9,6,2,1],[9,6,4,1],[9,7,2,1],
    #            [9,7,3,1],[9,7,4,1],[9,7,5,1],[10,3,2,1],[10,4,2,1],[10,4,3,1],[10,5,2,1],[10,5,3,1],[10,5,4,1],
    #            [10,6,2,1],[10,6,3,1],[10,6,4,1],[10,6,5,1]
    #            ]
    for check in checklist:
        print(check)
        Writefile(generate(*check))
        for command in commands:
            subprocess.run(command, shell=True)
        tmp=[str(i) for i in check]
        file.write("Enrollment:\n"+",".join(tmp)+"\n")
        
        try:
            file.write("CPE and score:\n")
            with open("result", "r", encoding="utf-8") as f:
                content=f.readlines()[-2::]
                file.write("".join(content))
        except Exception as e:
            print(f"Error! In open result or read result! Check{check}! Error as follows:\n {e} ")
            file.write("\n")
        try:
            file.write("correct:\n")
            with open("correct", "r", encoding="utf-8") as f:
                content=f.readlines()[-1::]
                file.write("".join(content))
        except Exception as e:
            print(f"Error! In open correct or read correct! Check{check}! Error as follows:\n {e} ")
            file.write("\n")
        try:
            file.write("lenth:\n")
            with open("lenth", "r", encoding="utf-8") as f:
                content=f.readlines()[-1::]
                file.write("".join(content))
        except Exception as e:
            print(f"Error! In open lenth or read lenth! Check{check}! Error as follows:\n {e} ")
            file.write("\n")
        file.write("#"*10+"\n")
    file.close()

    #clean
    subprocess.run("rm lenth correct result")


if __name__=="__main__":
    # generate 根据给定的展开序列进行展开，注意程序并不会特别检查输入的序列是否合理！（只有简单的判断）
    # generate 会返回 ncopy.yo的可修改部分（字符串）
    print(generate(8,4,2,1))
    
    # writefile 会直接生成ncopy.ys文件（不包含name+ID）,结合命令快速检测`(python3 archlabfinal.py; ./correctness.pl; ./benchmark; ./check-len.pl < ncopy.yo)`
    Writefile(generate(8,4,2,1))

    #seekBest会比较函数内部设定的展开序列列表（需自己修改），并生成结果文件comparison.txt
    seekBest()