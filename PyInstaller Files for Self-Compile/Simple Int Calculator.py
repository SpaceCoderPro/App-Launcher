print()
print("Simple Int Calculator Version 1.0")
print("By Samyak")
print()
print("Use Format: When prompted for number 1, input initial number")
print("When prompted for operant: You can input any of following: *,/,+,-")
print("When prompted for number 2, enter your second number")
print()

number1=int(input("Input Number 1: "))
operant=input("Input Operant: ")
number2=int(input("Input Number 2: "))

if operant=="/":
    output=number1/number2
elif operant=="*":
    output=number1*number2
elif operant=="+":
    output=number1+number2
elif operant=="-":
    output=number1-number2

print("The Output is: ", output)
i=input("Press enter to exit")