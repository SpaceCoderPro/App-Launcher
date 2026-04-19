print()
print("Full Calculator Fast 1.0")
print("By Samyak")
print()
CurrentOp=input("Enter Initial Operation in format 1+1: ")
CurrentVal=eval(CurrentOp)
Go = True
print("Input All next expressions in the format /2")
print("Input 'S' to stop Calculation Loop")
while Go:
    CurrentOp=input("Next Expression: ")
    if CurrentOp.lower()=="s":
        break
    operant=CurrentOp[0]
    number1=CurrentVal
    number2=int(CurrentOp[1:])
    if operant=="/":
        output=number1/number2
    elif operant=="*":
        output=number1*number2
    elif operant=="+":
        output=number1+number2
    elif operant=="-":
        output=number1-number2
    CurrentVal=output
print("Final Answer: ", CurrentVal)
i=input("Press enter to exit")
