from fastmcp import FastMCP
import random

#create server
mcp=FastMCP(name="Remote Demo Server")

@mcp.tool
def roll_dance(n_dice :int=1)->list[int]:
    """Roll n_dice and return the results"""
    return [random.randint(1,6) for _ in range(n_dice)]

@mcp.tool
def multiply_number(a:float, b :float)->float:
     """Multiply two numbers"""
     return a*b
              
if __name__ == "__main__":
  mcp.run(transport="http",host="0.0.0.0",port=8000)
